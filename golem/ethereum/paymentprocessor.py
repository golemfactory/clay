import logging
import sys
import time
import json
from os import path

from .accounts import Account
from .contracts import TestGNT
from .node import tETH_faucet_donate

from time import sleep
from pydispatch import dispatcher

from ethereum import abi, utils
from ethereum.transactions import Transaction
from ethereum.utils import denoms

from golem.ethereum import Client
from golem.model import db, Payment, PaymentStatus
from golem.transactions.service import Service
from golem.utils import decode_hex, encode_hex

log = logging.getLogger("golem.pay")

gnt_contract = abi.ContractTranslator(json.loads(TestGNT.ABI))


def _encode_payments(payments):
    paymap = {}
    for p in payments:
        if p.payee in paymap:
            paymap[p.payee] += p.value
        else:
            paymap[p.payee] = p.value

    args = []
    value = 0
    for to, v in paymap.items():
        max_value = 2 ** 96
        if v >= max_value:
            raise ValueError("v should be less than {}".format(max_value))
        value += v
        v = utils.zpad(utils.int_to_big_endian(v), 12)
        pair = v + to
        if len(pair) != 32:
            raise ValueError(
                "Incorrect pair length: {}. Should be 32".format(len(pair))
            )
        args.append(pair)
    return args, value


def is_nonempty_file(file_path: str) -> bool:
    return path.isfile(file_path) and path.getsize(file_path) > 0


class PaymentProcessor(Service):
    # Default deadline in seconds for new payments.
    DEFAULT_DEADLINE = 10 * 60

    # Gas price: 20 shannons, Homestead suggested gas price.
    GAS_PRICE = 20 * 10 ** 9

    # Max gas cost for a single payment. Estimated in tests.
    SINGLE_PAYMENT_GAS_COST = 60000

    SINGLE_PAYMENT_ETH_COST = GAS_PRICE * SINGLE_PAYMENT_GAS_COST

    # Gas reservation for performing single batch payment.
    # TODO: Adjust this value later and add MAX_PAYMENTS limit.
    GAS_RESERVATION = 21000 + 1000 * 50000

    TESTGNT_ADDR = decode_hex("7295bB8709EC1C22b758A8119A4214fFEd016323")

    SYNC_CHECK_INTERVAL = 10

    def __init__(self, client: Client, account_password: bytes, faucet=False) \
            -> None:
        self.__client = client
        self.__eth_balance = None
        self.__gnt_balance = None
        self.__gnt_reserved = 0
        self._awaiting = []  # type: List[Any] # Awaiting individual payments
        self._inprogress = {}  # type: Dict[Any,Any] # Sent transactions.
        self.__last_sync_check = time.time()
        self.__sync = False
        self.__temp_sync = False
        self.__faucet = faucet
        self.__testGNT = abi.ContractTranslator(json.loads(TestGNT.ABI))
        self._waiting_for_faucet = False
        self.deadline = sys.maxsize
        self.load_from_db()
        super(PaymentProcessor, self).__init__(13)

        if len(account_password) == 0:
            raise ValueError("Empty password provided")

        keystore_file = path.join(client.node.datadir,
                                  'golem_ethereum_account.json')
        t = time.clock()
        if is_nonempty_file(keystore_file):
            log.debug("Loading existing account: {}".format(keystore_file))
            self.account = Account.load(keystore_file, account_password)
        else:
            self.account = Account.new(account_password, path=keystore_file)
            self.account.save()
        log.info("Account {} unlocked ({})".format(self.account.address.hex(),
                                                   self.account.path))
        log.debug("Unlock time: {} s".format(time.clock() - t))

    def wait_until_synchronized(self):
        is_synchronized = False
        while not is_synchronized:
            try:
                is_synchronized = self.is_synchronized()
            except Exception as e:
                log.error("Error "
                          "while syncing with eth blockchain: "
                          "{}".format(e))
                is_synchronized = False
            else:
                sleep(self.SYNC_CHECK_INTERVAL)

        return True

    def is_synchronized(self):
        """ Checks if the Ethereum node is in sync with the network."""

        if time.time() - self.__last_sync_check <= self.SYNC_CHECK_INTERVAL:
            # When checking again within 10 s return previous status.
            # This also handles geth issue where synchronization starts after
            # 10 s since the node was started.
            return self.__sync
        self.__last_sync_check = time.time()

        def check():
            peers = self.__client.get_peer_count()
            log.info("Peer count: {}".format(peers))
            if peers == 0:
                return False
            if self.__client.is_syncing():
                log.info("Node is syncing...")
                syncing = self.__client.web3.eth.syncing
                if syncing:
                    log.info("currentBlock: " + str(syncing['currentBlock']) +
                             "\t highestBlock:" + str(syncing['highestBlock']))
                return False
            return True

        # TODO: This can be improved now because we use Ethereum Ropsten.
        # Normally we should check the time of latest block, but Golem testnet
        # does not produce block regularly. The workaround is to wait for 2
        # confirmations.
        if not check():
            # Reset both sync flags. We have to start over.
            self.__temp_sync = False
            self.__sync = False
            return False

        if not self.__temp_sync:
            # Set the first flag. We will check again in SYNC_CHECK_INTERVAL s.
            self.__temp_sync = True
            return False

        if not self.__sync:
            # Second confirmation of being in sync. We are sure.
            self.__sync = True
            log.info("Synchronized!")

        return True

    def eth_address(self, zpad=True):
        raw = self.account.address
        # TODO: Hack RPC client to allow using raw address.
        if zpad:
            raw = utils.zpad(raw, 32)
        return '0x' + encode_hex(raw)

    def balance_known(self):
        return self.__gnt_balance is not None and self.__eth_balance is not None

    def eth_balance(self, refresh=False):
        # FIXME: The balance must be actively monitored!
        if self.__eth_balance is None or refresh:
            addr = self.eth_address(zpad=False)
            self.__eth_balance = self.__client.get_balance(addr)
            log.info("ETH: {}".format(self.__eth_balance / denoms.ether))
        return self.__eth_balance

    def gnt_balance(self, refresh=False):
        if self.__gnt_balance is None or refresh:
            addr = self.account.address
            data = self.__testGNT.encode('balanceOf', (addr,))
            r = self.__client.call(_from='0x' + encode_hex(addr),
                                   to='0x' + encode_hex(self.TESTGNT_ADDR),
                                   data='0x' + encode_hex(data),
                                   block='pending')
            if r is None or r == '0x':
                self.__gnt_balance = 0
            else:
                self.__gnt_balance = int(r, 16)
            log.info("GNT: {}".format(self.__gnt_balance / denoms.ether))
        return self.__gnt_balance

    def _eth_reserved(self):
        # Here we keep the same simple estimation by number of atomic payments.
        # FIXME: This is different than estimation in sendout(). Create
        #        helpers for estimation and stick to them.
        num_payments = len(self._awaiting) + sum(len(p) for p in
                                                 self._inprogress.values())
        return num_payments * self.SINGLE_PAYMENT_ETH_COST

    def _eth_available(self):
        """ Returns available ETH balance for new payments fees."""
        return self.eth_balance() - self._eth_reserved()

    def _gnt_reserved(self):
        return self.__gnt_reserved

    def _gnt_available(self):
        return self.gnt_balance() - self.__gnt_reserved

    def load_from_db(self):
        with db.atomic():
            for sent_payment in Payment \
                    .select() \
                    .where(Payment.status == PaymentStatus.sent):
                transaction_hash = decode_hex(sent_payment.details.tx)
                if transaction_hash not in self._inprogress:
                    self._inprogress[transaction_hash] = []
                self._inprogress[transaction_hash].append(sent_payment)
            for awaiting_payment in Payment \
                    .select() \
                    .where(Payment.status == PaymentStatus.awaiting):
                self.add(awaiting_payment)

    def add(self, payment, deadline=DEFAULT_DEADLINE):
        if payment.status is not PaymentStatus.awaiting:
            raise RuntimeError(
                "Invalid payment status: {}".format(payment.status))

        log.info("Payment {:.6} to {:.6} ({:.6f})".format(
            payment.subtask,
            encode_hex(payment.payee),
            payment.value / denoms.ether))

        # Check if enough ETH available to pay the gas cost.
        if self._eth_available() < self.SINGLE_PAYMENT_ETH_COST:
            log.warning("Low ETH: {} available".format(self._eth_available()))
            return False

        av_gnt = self._gnt_available()
        if av_gnt < payment.value:
            log.warning("Low GNT: {:.6f}".format(av_gnt / denoms.ether))
            return False

        self._awaiting.append(payment)
        self.__gnt_reserved += payment.value

        # Set new deadline if not set already or shorter than the current one.
        # TODO: Optimize by checking the time once per service update.
        new_deadline = int(time.time()) + deadline
        if new_deadline < self.deadline:
            self.deadline = new_deadline

        log.info("GNT: available {:.6f}, reserved {:.6f}".format(
            av_gnt / denoms.ether, self.__gnt_reserved / denoms.ether))
        return True

    def sendout(self):
        if not self._awaiting:
            return False

        now = int(time.time())
        if self.deadline > now:
            log.info("Next sendout in {} s".format(self.deadline - now))
            return False

        payments = self._awaiting  # FIXME: Should this list be synchronized?
        self._awaiting = []
        self.deadline = sys.maxsize
        addr = self.eth_address(zpad=False)
        nonce = self.__client.get_transaction_count(addr)
        p, value = _encode_payments(payments)
        data = gnt_contract.encode('batchTransfer', [p])
        gas = 21000 + 800 + len(p) * 30000
        tx = Transaction(nonce, self.GAS_PRICE, gas, to=self.TESTGNT_ADDR,
                         value=0, data=data)
        tx.sign(self.account.privkey)
        h = tx.hash
        log.info("Batch payments: {:.6}, value: {:.6f}"
                 .format(encode_hex(h), value / denoms.ether))

        # Firstly write transaction hash to database. We need the hash to be
        # remembered before sending the transaction to the Ethereum node in
        # case communication with the node is interrupted and it will be not
        # known if the transaction has been sent or not.
        with Payment._meta.database.transaction():
            for payment in payments:
                payment.status = PaymentStatus.sent
                payment.details.tx = encode_hex(h)
                payment.save()
                log.debug("- {} send to {} ({:.6f})".format(
                    payment.subtask,
                    encode_hex(payment.payee),
                    payment.value / denoms.ether))

            tx_hash = self.__client.send(tx)
            tx_hex = decode_hex(tx_hash)
            if tx_hex != h:  # FIXME: Improve Client.
                raise RuntimeError("Incorrect tx hash: {}, should be: {}"
                                   .format(tx_hex, h))

            self._inprogress[h] = payments

        # Remove from reserved, because we monitor the pending block.
        # TODO: Maybe we should only monitor the latest block?
        self.__gnt_reserved -= value
        return True

    def monitor_progress(self):
        confirmed = []
        for h, payments in self._inprogress.items():
            hstr = '0x' + encode_hex(h)
            log.info("Checking {:.6} tx [{}]".format(hstr, len(payments)))
            receipt = self.__client.get_transaction_receipt(hstr)
            if receipt:
                block_hash = receipt['blockHash'][2:]
                if len(block_hash) != 64:
                    raise ValueError(
                        "block hash length should be 64, but is: {}".format(
                            len(block_hash)))
                block_number = receipt['blockNumber']
                gas_used = receipt['gasUsed']
                total_fee = gas_used * self.GAS_PRICE
                fee = total_fee // len(payments)
                log.info("Confirmed {:.6}: block {} ({}), gas {}, fee {}"
                         .format(hstr, block_hash, block_number, gas_used, fee))
                with Payment._meta.database.transaction():
                    for p in payments:
                        p.status = PaymentStatus.confirmed
                        p.details.block_number = block_number
                        p.details.block_hash = block_hash
                        p.details.fee = fee
                        p.save()
                        dispatcher.send(
                            signal='golem.monitor',
                            event='payment',
                            addr=encode_hex(p.payee),
                            value=p.value
                        )
                        dispatcher.send(
                            signal='golem.paymentprocessor',
                            event='payment.confirmed',
                            payment=p
                        )
                        log.debug(
                            "- %.6f confirmed fee %.6f",
                            p.subtask,
                            fee / denoms.ether
                        )
                confirmed.append(h)
        for h in confirmed:
            # Delete in progress entry.
            del self._inprogress[h]

    def get_ether_from_faucet(self):
        if self.__faucet and self.eth_balance(True) < 10 ** 15:
            log.info("Requesting tETH")
            tETH_faucet_donate(self.account.address)
            return False
        return True

    def get_gnt_from_faucet(self):
        if self.__faucet and self.gnt_balance(True) < 100 * denoms.ether:
            log.info("Requesting tGNT")
            addr = self.eth_address(zpad=False)
            nonce = self.__client.get_transaction_count(addr)
            data = self.__testGNT.encode_function_call('create', ())
            tx = Transaction(nonce, self.GAS_PRICE, 90000, to=self.TESTGNT_ADDR,
                             value=0, data=data)
            tx.sign(self.account.privkey)
            self.__client.send(tx)
            return False
        return True

    def get_logs(self,
                 from_block=None,
                 to_block=None,
                 address=None,
                 topics=None):

        return self.__client.get_logs(from_block=from_block,
                                      to_block=to_block,
                                      address=address,
                                      topics=topics)

    def _run(self):
        if self._waiting_for_faucet:
            return

        self._waiting_for_faucet = True

        try:
            if self.is_synchronized() and \
                    self.get_ether_from_faucet() and \
                    self.get_gnt_from_faucet():
                self.monitor_progress()
                self.sendout()
        finally:
            self._waiting_for_faucet = False

    def stop(self):
        super(PaymentProcessor, self).stop()
        self.__client._kill_node()
