from __future__ import division

import logging
import sys
import time

from ethereum import abi, keys, utils
from ethereum.transactions import Transaction
from ethereum.utils import denoms
from pydispatch import dispatcher

from golem.model import Payment, PaymentStatus
from golem.transactions.service import Service
from .contracts import TestGNT
from .node import ropsten_faucet_donate

log = logging.getLogger("golem.pay")

gnt_contract = abi.ContractTranslator(TestGNT.ABI)


def _encode_payments(payments):
    paymap = {}
    for p in payments:
        if p.payee in paymap:
            paymap[p.payee] += p.value
        else:
            paymap[p.payee] = p.value

    args = []
    value = 0L
    for to, v in paymap.iteritems():
        max_value = 2 ** 96
        if v >= max_value:
            raise ValueError("v should be less than {}".format(max_value))
        value += v
        v = utils.zpad(utils.int_to_big_endian(v), 12)
        pair = v + to
        if len(pair) != 32:
            raise ValueError("Incorrect pair length: {}. Should be 32".format(len(pair)))
        args.append(pair)
    return args, value


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

    TESTGNT_ADDR = "689ed42Ec0C3b3B799Dc5659725Bf536635F45d1".decode('hex')

    SYNC_CHECK_INTERVAL = 10

    def __init__(self, client, privkey, faucet=False):
        self.__client = client
        self.__privkey = privkey
        self.__eth_balance = None
        self.__gnt_balance = None
        self.__gnt_reserved = 0
        self.__awaiting = []  # Awaiting individual payments
        self.__inprogress = {}  # Sent transactions.
        self.__last_sync_check = time.time()
        self.__sync = False
        self.__temp_sync = False
        self.__faucet = faucet
        self.__testGNT = abi.ContractTranslator(TestGNT.ABI)
        self._waiting_for_faucet = False
        self.deadline = sys.maxsize
        super(PaymentProcessor, self).__init__(13)

    def synchronized(self):
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

    def balance_known(self):
        return self.__gnt_balance is not None and self.__eth_balance is not None

    def eth_balance(self, refresh=False):
        # FIXME: The balance must be actively monitored!
        if self.__eth_balance is None or refresh:
            addr = keys.privtoaddr(self.__privkey)
            # TODO: Hack RPC client to allow using raw address.
            addr = '0x' + addr.encode('hex')
            self.__eth_balance = self.__client.get_balance(addr)
            log.info("ETH: {}".format(self.__eth_balance / denoms.ether))
        return self.__eth_balance

    def gnt_balance(self, refresh=False):
        if self.__gnt_balance is None or refresh:
            addr = keys.privtoaddr(self.__privkey)
            data = self.__testGNT.encode('balanceOf', (addr, ))
            r = self.__client.call(_from='0x' + addr.encode('hex'),
                                   to='0x' + self.TESTGNT_ADDR.encode('hex'),
                                   data='0x' + data.encode('hex'),
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
        num_payments = len(self.__awaiting) + sum(len(p) for p in self.__inprogress.values())
        return num_payments * self.SINGLE_PAYMENT_ETH_COST

    def _eth_available(self):
        """ Returns available ETH balance for new payments fees."""
        return self.eth_balance() - self._eth_reserved()

    def _gnt_reserved(self):
        return self.__gnt_reserved

    def _gnt_available(self):
        return self.gnt_balance() - self.__gnt_reserved

    def add(self, payment, deadline=DEFAULT_DEADLINE):
        if payment.status is not PaymentStatus.awaiting:
            raise RuntimeError("Invalid payment status: {}".format(payment.status))

        log.info("Payment {:.6} to {:.6} ({:.6f})".format(
            payment.subtask,
            payment.payee.encode('hex'),
            payment.value / denoms.ether))

        # Check if enough ETH available to pay the gas cost.
        if self._eth_available() < self.SINGLE_PAYMENT_ETH_COST:
            log.warning("Low ETH: {} available".format(self._eth_available()))
            return False

        av_gnt = self._gnt_available()
        if av_gnt < payment.value:
            log.warning("Low GNT: {:.6f}".format(av_gnt / denoms.ether))
            return False

        self.__awaiting.append(payment)
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
        if not self.__awaiting:
            return False

        now = int(time.time())
        if self.deadline > now:
            log.info("Next sendout in {} s".format(self.deadline - now))
            return False

        payments = self.__awaiting  # FIXME: Should this list be synchronized?
        self.__awaiting = []
        self.deadline = sys.maxsize
        addr = keys.privtoaddr(self.__privkey)  # TODO: Should be done once?
        nonce = self.__client.get_transaction_count('0x' + addr.encode('hex'))
        p, value = _encode_payments(payments)
        data = gnt_contract.encode('batchTransfer', [p])
        gas = 21000 + 800 + len(p) * 30000
        tx = Transaction(nonce, self.GAS_PRICE, gas, to=self.TESTGNT_ADDR,
                         value=0, data=data)
        tx.sign(self.__privkey)
        h = tx.hash
        log.info("Batch payments: {:.6}, value: {:.6f}"
                 .format(h.encode('hex'), value / denoms.ether))

        # Firstly write transaction hash to database. We need the hash to be
        # remembered before sending the transaction to the Ethereum node in
        # case communication with the node is interrupted and it will be not
        # known if the transaction has been sent or not.
        with Payment._meta.database.transaction():
            for payment in payments:
                payment.status = PaymentStatus.sent
                payment.details['tx'] = h.encode('hex')
                payment.save()
                log.debug("- {} send to {} ({:.6f})".format(
                    payment.subtask,
                    payment.payee.encode('hex'),
                    payment.value / denoms.ether))

            tx_hash = self.__client.send(tx)
            if tx_hash[2:].decode('hex') != h:  # FIXME: Improve Client.
                raise RuntimeError("Incorrect tx hash: {}, should be: {}"
                                   .format(tx_hash[2:].decode('hex'), h))

            self.__inprogress[h] = payments

        # Remove from reserved, because we monitor the pending block.
        # TODO: Maybe we should only monitor the latest block?
        self.__gnt_reserved -= value
        return True

    def monitor_progress(self):
        confirmed = []
        for h, payments in self.__inprogress.iteritems():
            hstr = '0x' + h.encode('hex')
            log.info("Checking {:.6} tx [{}]".format(hstr, len(payments)))
            receipt = self.__client.get_transaction_receipt(hstr)
            if receipt:
                block_hash = receipt['blockHash'][2:]
                if len(block_hash) != 64:
                    raise ValueError("block hash length should be 64, but is: {}".format(len(block_hash)))
                block_number = receipt['blockNumber']
                gas_used = receipt['gasUsed']
                total_fee = gas_used * self.GAS_PRICE
                fee = total_fee // len(payments)
                log.info("Confirmed {:.6}: block {} ({}), gas {}, fee {}"
                         .format(hstr, block_hash, block_number, gas_used, fee))
                with Payment._meta.database.transaction():
                    for p in payments:
                        p.status = PaymentStatus.confirmed
                        p.details['block_number'] = block_number
                        p.details['block_hash'] = block_hash
                        p.details['fee'] = fee
                        p.save()
                        dispatcher.send(signal='golem.monitor', event='payment', addr=p.payee.encode('hex'), value=p.value)
                        dispatcher.send(signal='golem.paymentprocessor', event='payment.confirmed', payment=p)
                        log.debug("- {:.6} confirmed fee {:.6f}".format(p.subtask,
                                                                        fee / denoms.ether))
                confirmed.append(h)
        for h in confirmed:
            # Delete in progress entry.
            del self.__inprogress[h]

    def get_ether_from_faucet(self):
        if self.__faucet and self.eth_balance(True) == 0:
            addr = keys.privtoaddr(self.__privkey)
            ropsten_faucet_donate(addr)
            return False
        return True

    def get_gnt_from_faucet(self):
        if self.__faucet and self.gnt_balance(True) < 100 * denoms.ether:
            log.info("Requesting tGNT")
            addr = keys.privtoaddr(self.__privkey)
            nonce = self.__client.get_transaction_count('0x' + addr.encode('hex'))
            data = self.__testGNT.encode_function_call('create', ())
            tx = Transaction(nonce, self.GAS_PRICE, 90000, to=self.TESTGNT_ADDR,
                             value=0, data=data)
            tx.sign(self.__privkey)
            self.__client.send(tx)
            return False
        return True

    def _run(self):
        if self._waiting_for_faucet:
            return

        self._waiting_for_faucet = True

        try:
            if self.synchronized() and \
                    self.get_ether_from_faucet() and \
                    self.get_gnt_from_faucet():
                self.monitor_progress()
                self.sendout()
        finally:
            self._waiting_for_faucet = False
