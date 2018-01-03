import abc
import json
import logging
import sys
import time
from threading import Lock
from time import sleep
from typing import Any, List

from ethereum import abi, utils, keys
from ethereum.transactions import Transaction
from ethereum.utils import denoms
from pydispatch import dispatcher

from golem.core.service import LoopingCallService
from golem.ethereum import Client
from golem.model import db, Payment, PaymentStatus
from golem.utils import decode_hex, encode_hex
from .contracts import TestGNT
from .contracts import gntw
from .node import tETH_faucet_donate

log = logging.getLogger("golem.pay")


def encode_payments(payments: List[Payment]):
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
                "Incorrect pair length: {}. Should be 32".format(len(pair)))
        args.append(pair)
    return args


class AbstractToken(object, metaclass=abc.ABCMeta):
    """
    This is a common interface for token transactions. It hides whether we're
    using GNT or GNTW underneath.
    """
    def __init__(self, client: Client):
        self._client = client

    def _create_transaction(self,
                            sender: str,
                            token_address,
                            data,
                            gas: int) -> Transaction:
        nonce = self._client.get_transaction_count(sender)
        tx = Transaction(nonce,
                         PaymentProcessor.GAS_PRICE,
                         gas,
                         to=token_address,
                         value=0,
                         data=data)
        return tx

    def _send_transaction(self,
                          privkey: bytes,
                          token_address,
                          data,
                          gas: int) -> Transaction:
        tx = self._create_transaction(
            '0x' + encode_hex(keys.privtoaddr(privkey)),
            token_address,
            data,
            gas)
        tx.sign(privkey)
        self._client.send(tx)
        return tx

    def _get_balance(self, token_abi, token_address, addr: str) -> int:
        data = token_abi.encode_function_call('balanceOf', [addr])
        r = self._client.call(
            _from='0x' + encode_hex(addr),
            to='0x' + encode_hex(token_address),
            data='0x' + encode_hex(data),
            block='pending')
        if r is None:
            return None
        return 0 if r == '0x' else int(r, 16)

    def _request_from_faucet(self,
                             token_abi,
                             token_address,
                             privkey: bytes) -> None:
        data = token_abi.encode_function_call('create', [])
        self._send_transaction(privkey, token_address, data, 90000)

    @abc.abstractmethod
    def get_balance(self, addr: str) -> int:
        pass

    @abc.abstractmethod
    def batch_transfer(self,
                       privkey: bytes,
                       payments: List[Payment]) -> Transaction:
        """
        Takes a list of payments to be made and returns prepared transaction
        for the batch payment. The transaction is not sent, but it is signed.
        It may return None when it's unable to make transaction at the moment,
        but this shouldn't be treated as an error. In case of GNTW sometimes
        we need to do some preparations (like convertion from GNT) before
        we can make a batch transfer.
        """
        pass

    @abc.abstractmethod
    def get_incomes_from_block(self, block: int, address) -> List[Any]:
        pass


class GNTToken(AbstractToken):
    """
    When the main token and the batchTransfer function are in the same contract.
    Which is the case for tGNT in testnet and eventually (after migration)
    will be the case for the new GNT in the mainnet as well.
    """
    TESTGNT_ADDR = decode_hex("7295bB8709EC1C22b758A8119A4214fFEd016323")

    # keccak256(Transfer(address,address,uint256))
    TRANSFER_EVENT_ID = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'  # noqa

    def __init__(self, client: Client):
        super().__init__(client)
        self.__testGNT = abi.ContractTranslator(json.loads(TestGNT.ABI))

    def get_balance(self, addr: str) -> int:
        balance = self._get_balance(
            self.__testGNT,
            self.TESTGNT_ADDR,
            decode_hex(addr))
        if balance is not None:
            log.info("TestGNT: {}".format(balance / denoms.ether))
        return balance

    def request_from_faucet(self, privkey: bytes) -> None:
        self._request_from_faucet(self.__testGNT, self.TESTGNT_ADDR, privkey)

    def batch_transfer(self,
                       privkey: bytes,
                       payments: List[Payment]) -> Transaction:
        p = encode_payments(payments)
        data = self.__testGNT.encode_function_call('batchTransfer', [p])
        gas = PaymentProcessor.GAS_BATCH_PAYMENT_BASE + \
            len(p) * PaymentProcessor.GAS_PER_PAYMENT
        tx = self._create_transaction(
            '0x' + encode_hex(keys.privtoaddr(privkey)),
            self.TESTGNT_ADDR,
            data,
            gas)
        tx.sign(privkey)
        return tx

    def get_incomes_from_block(self, block: int, address) -> List[Any]:
        logs = self._client.get_logs(block,
                                     block,
                                     '0x' + encode_hex(self.TESTGNT_ADDR),
                                     [self.TRANSFER_EVENT_ID, None, address])
        if not logs:
            return logs

        res = []
        for entry in logs:
            if entry['topics'][2] != address:
                raise Exception("Unexpected income event from {}"
                                .format(entry['topics'][2]))

            res.append({
                'sender': entry['topics'][1],
                'value': int(entry['data'], 16),
            })
        return res


class GNTWToken(AbstractToken):
    """
    When batchTransfer function is in a different contract than the main token.
    GNTW implementation specifically.
    """
    GNTW_ADDRESS = decode_hex("a8CD649dB30b963592D88FdE95fe6284d6224329")
    TESTGNT_ADDRESS = decode_hex("2928aA793B79FCdb7b5B94f5d8419e0EE20AbDaF")
    FAUCET_ADDRESS = decode_hex("36FeE1616A131E7382922475A1BA67F88F891f0d")

    # keccak256(BatchTransfer(address,address,uint256,uint64))
    TRANSFER_EVENT_ID = '0x24310ec9df46c171fe9c6d6fe25cac6781e7fa8f153f8f72ce63037a4b38c4b6'  # noqa

    CREATE_PERSONAL_DEPOSIT_GAS = 320000
    PROCESS_DEPOSIT_GAS = 110000
    GNT_TRANSFER_GAS = 55000

    def __init__(self, client: Client):
        super().__init__(client)
        self.__gntw = abi.ContractTranslator(
            json.loads(gntw.GolemNetworkTokenWrapped.ABI))
        self.__gnt = abi.ContractTranslator(
            json.loads(gntw.GolemNetworkToken.ABI))
        self.__faucet = abi.ContractTranslator(json.loads(gntw.Faucet.ABI))
        self.__deposit_address = None
        self.__deposit_address_created = False
        self.__process_deposit_tx = None

    def get_balance(self, addr: str) -> int:
        gnt_balance = self._get_balance(self.__gnt, self.TESTGNT_ADDRESS, addr)
        if gnt_balance is None:
            return None

        gntw_balance = self._get_balance(self.__gntw, self.GNTW_ADDRESS, addr)
        if gntw_balance is None:
            return None

        log.info("TestGNT: {} GNTW: {}".format(
            gnt_balance / denoms.ether,
            gntw_balance / denoms.ether))
        return gnt_balance + gntw_balance

    def request_from_faucet(self, privkey: bytes) -> None:
        self._request_from_faucet(self.__faucet, self.FAUCET_ADDRESS, privkey)

    def batch_transfer(self,
                       privkey: bytes,
                       payments: List[Payment]) -> Transaction:
        if self.__process_deposit_tx:
            hstr = '0x' + encode_hex(self.__process_deposit_tx)
            receipt = self._client.get_transaction_receipt(hstr)
            if not receipt:
                log.info("Waiting to process deposit")
                return None
            self.__process_deposit_tx = None

        gntw_balance = self._get_balance(
            self.__gntw,
            self.GNTW_ADDRESS,
            '0x' + encode_hex(keys.privtoaddr(privkey)))
        if gntw_balance is None:
            return None
        total_value = sum([p.value for p in payments])
        if gntw_balance < total_value:
            log.info("Not enough GNTW, trying to convert GNT. "
                     "GNTW: {}, total_value: {}"
                     .format(gntw_balance, total_value))
            self.__convert_gnt(privkey)
            return None

        p = encode_payments(payments)
        # TODO: closure time should be the timestamp of the youngest payment
        # from the batch
        closure_time = int(time.time())
        data = self.__gntw.encode_function_call('batchTransfer',
                                                [p, closure_time])
        gas = PaymentProcessor.GAS_BATCH_PAYMENT_BASE + \
            len(p) * PaymentProcessor.GAS_PER_PAYMENT
        return self._create_transaction(privkey, self.GNTW_ADDRESS, data, gas)

    def get_incomes_from_block(self, block: int, address) -> List[Any]:
        logs = self._client.get_logs(block,
                                     block,
                                     '0x' + encode_hex(self.GNTW_ADDRESS),
                                     [self.TRANSFER_EVENT_ID, None, address])
        if not logs:
            return logs

        res = []
        for entry in logs:
            if entry['topics'][2] != address:
                raise Exception("Unexpected income event from {}"
                                .format(entry['topics'][2]))

            res.append({
                'sender': entry['topics'][1],
                'value': int(entry['data'][:66], 16),
            })
        return res

    def __get_deposit_address(self, privkey: bytes) -> bytes:
        if not self.__deposit_address:
            addr = keys.privtoaddr(privkey)
            data = self.__gntw.encode_function_call(
                'getPersonalDepositAddress',
                [addr])
            res = self._client.call(_from='0x' + encode_hex(addr),
                                    to='0x' + encode_hex(self.GNTW_ADDRESS),
                                    data='0x' + encode_hex(data),
                                    block='pending')
            if int(res, 16) != 0:
                self.__deposit_address = decode_hex(res)[-20:]
            elif not self.__deposit_address_created:
                data = self.__gntw.encode_function_call(
                    'createPersonalDepositAddress',
                    [])
                tx = self._send_transaction(privkey,
                                            self.GNTW_ADDRESS,
                                            data,
                                            self.CREATE_PERSONAL_DEPOSIT_GAS)
                log.info("Create personal deposit address tx: {}"
                         .format(encode_hex(tx.hash)))
                self.__deposit_address_created = True
        return self.__deposit_address

    def __convert_gnt(self, privkey: bytes) -> None:
        gnt_balance = self._get_balance(
            self.__gnt,
            self.TESTGNT_ADDRESS,
            '0x' + encode_hex(keys.privtoaddr(privkey)))
        if gnt_balance is None:
            return

        log.info("Converting {} GNT to GNTW".format(gnt_balance))
        pda = self.__get_deposit_address(privkey)
        if not pda:
            log.info("Not converting until deposit address is known")
            return

        data = self.__gnt.encode_function_call(
            'transfer',
            [self.__deposit_address, gnt_balance])
        tx = self._send_transaction(privkey,
                                    self.TESTGNT_ADDRESS,
                                    data,
                                    self.GNT_TRANSFER_GAS)
        log.info("Transfer GNT to personal deposit tx: {}"
                 .format(encode_hex(tx.hash)))

        data = self.__gntw.encode_function_call('processDeposit', [])
        tx = self._send_transaction(privkey,
                                    self.GNTW_ADDRESS,
                                    data,
                                    self.PROCESS_DEPOSIT_GAS)
        self.__process_deposit_tx = tx.hash
        log.info("Process deposit tx: {}".format(encode_hex(tx.hash)))


class PaymentProcessor(LoopingCallService):
    # Default deadline in seconds for new payments.
    DEFAULT_DEADLINE = 10 * 60

    # Gas price: 20 gwei, Homestead suggested gas price.
    GAS_PRICE = 20 * 10 ** 9

    # Total gas for a batchTransfer is BASE + len(payments) * PER_PAYMENT
    GAS_PER_PAYMENT = 30000
    ETH_PER_PAYMENT = GAS_PRICE * GAS_PER_PAYMENT
    # tx: 21000, balance substract: 5000, arithmetics < 800
    GAS_BATCH_PAYMENT_BASE = 21000 + 800 + 5000
    ETH_BATCH_PAYMENT_BASE = GAS_PRICE * GAS_BATCH_PAYMENT_BASE

    # Time required to reset the current balance when errors occur
    BALANCE_RESET_TIMEOUT = 30

    SYNC_CHECK_INTERVAL = 10

    # Minimal number of confirmations before we treat transactions as done
    REQUIRED_CONFIRMATIONS = 12

    def __init__(self,
                 client: Client,
                 privkey,
                 faucet=False,
                 token_factory=GNTToken) -> None:
        self.__token = token_factory(client)
        self.__client = client
        self.__privkey = privkey
        self.__eth_balance = None
        self.__gnt_balance = None
        self.__eth_reserved = 0
        self.__gnt_reserved = 0
        self.__eth_update_ts = 0
        self.__gnt_update_ts = 0
        self._awaiting_lock = Lock()
        self._awaiting = []  # type: List[Any] # Awaiting individual payments
        self._inprogress = {}  # type: Dict[Any,Any] # Sent transactions.
        self.__last_sync_check = time.time()
        self.__sync = False
        self.__temp_sync = False
        self.__faucet = faucet
        self._waiting_for_faucet = False
        self.deadline = sys.maxsize
        self.load_from_db()
        super(PaymentProcessor, self).__init__(13)

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
        raw = keys.privtoaddr(self.__privkey)
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
            self._update_eth_balance(self.__client.get_balance(addr))
            log.info("ETH: {}".format(self.__eth_balance / denoms.ether))
        return self.__eth_balance

    def gnt_balance(self, refresh=False):
        if self.__gnt_balance is None or refresh:
            gnt_balance = self.__token.get_balance(self.eth_address(zpad=False))
            self._update_gnt_balance(gnt_balance)
        return self.__gnt_balance

    def _update_eth_balance(self, eth_balance):
        eth_balance = self._balance_value(eth_balance, self.__eth_update_ts)
        if eth_balance is None:
            return
        self.__eth_update_ts = time.time()
        self.__eth_balance = eth_balance

    def _update_gnt_balance(self, gnt_balance):
        gnt_balance = self._balance_value(gnt_balance, self.__gnt_update_ts)
        if gnt_balance is None:
            return
        self.__gnt_update_ts = time.time()
        self.__gnt_balance = gnt_balance

    @classmethod
    def _balance_value(cls, balance, last_update_ts):
        if balance is not None:
            return balance

        dt = time.time() - last_update_ts
        if dt >= cls.BALANCE_RESET_TIMEOUT:
            return 0

    def _eth_reserved(self):
        return self.__eth_reserved + self.ETH_BATCH_PAYMENT_BASE

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
        if self._eth_available() < self.ETH_PER_PAYMENT:
            log.warning("Low ETH: {} available".format(self._eth_available()))
            return False

        av_gnt = self._gnt_available()
        if av_gnt < payment.value:
            log.warning("Low GNT: {:.6f}".format(av_gnt / denoms.ether))
            return False

        with self._awaiting_lock:
            ts = int(time.time())
            if not payment.processed_ts:
                with Payment._meta.database.transaction():
                    payment.processed_ts = ts
                    payment.save()

            self._awaiting.append(payment)
            # TODO: Optimize by checking the time once per service update.
            self.deadline = min(self.deadline, ts + deadline)

        self.__gnt_reserved += payment.value
        self.__eth_reserved += self.ETH_PER_PAYMENT

        log.info("GNT: available {:.6f}, reserved {:.6f}".format(
            av_gnt / denoms.ether, self.__gnt_reserved / denoms.ether))
        return True

    def sendout(self):
        with self._awaiting_lock:
            if not self._awaiting:
                return False

            now = int(time.time())
            if self.deadline > now:
                log.info("Next sendout in {} s".format(self.deadline - now))
                return False

            payments = self._awaiting
            self._awaiting = []

        tx = self.__token.batch_transfer(self.__privkey, payments)
        if not tx:
            with self._awaiting_lock:
                payments.extend(self._awaiting)
                self._awaiting = payments
            return False

        tx.sign(self.__privkey)
        value = sum([p.value for p in payments])
        h = tx.hash
        log.info("Batch payments: {:.6}, value: {:.6f}"
                 .format(encode_hex(h), value / denoms.ether))

        # If awaiting payments are not empty it means a new payment has been
        # added between clearing the awaiting list and here. In that case
        # we shouldn't update the deadline to sys.maxsize.
        with self._awaiting_lock:
            if not self._awaiting:
                self.deadline = sys.maxsize

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
        self.__eth_reserved -= len(payments) * self.ETH_PER_PAYMENT
        return True

    def monitor_progress(self):
        if not self._inprogress:
            return

        confirmed = []
        failed = {}
        current_block = self.__client.get_block_number()

        for h, payments in self._inprogress.items():
            hstr = '0x' + encode_hex(h)
            log.info("Checking {:.6} tx [{}]".format(hstr, len(payments)))
            receipt = self.__client.get_transaction_receipt(hstr)
            if not receipt:
                continue

            block_hash = receipt['blockHash'][2:]
            if len(block_hash) != 64:
                raise ValueError(
                    "block hash length should be 64, but is: {}".format(
                        len(block_hash)))

            block_number = receipt['blockNumber']
            if current_block - block_number < self.REQUIRED_CONFIRMATIONS:
                continue

            # if the transaction failed for whatever reason we need to retry
            if receipt['status'] != '0x1':
                with Payment._meta.database.transaction():
                    for p in payments:
                        p.status = PaymentStatus.awaiting
                        p.save()
                failed[h] = payments
                log.warning("Failed transaction: {}".format(receipt))
                continue

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
            del self._inprogress[h]

        for h, payments in failed.items():
            del self._inprogress[h]
            for p in payments:
                self.add(p)

    def get_ether_from_faucet(self):
        if self.__faucet and self.eth_balance(True) < 0.01 * denoms.ether:
            log.info("Requesting tETH")
            addr = keys.privtoaddr(self.__privkey)
            tETH_faucet_donate(addr)
            return False
        return True

    def get_gnt_from_faucet(self):
        if self.__faucet and self.gnt_balance(True) < 100 * denoms.ether:
            log.info("Requesting GNT from faucet")
            self.__token.request_from_faucet(self.__privkey)
            return False
        return True

    def get_incomes_from_block(self, block, address):
        return self.__token.get_incomes_from_block(block, address)

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
