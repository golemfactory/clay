from __future__ import division

import logging
import time

from ethereum import abi, keys, utils
from ethereum.transactions import Transaction
from ethereum.utils import denoms
from twisted.internet.task import LoopingCall

from golem.model import Payment, PaymentStatus

from .contracts import BankOfDeposit
from .node import Faucet


log = logging.getLogger("golem.pay")

bank_contract = abi.ContractTranslator(BankOfDeposit.ABI)


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
        value += v
        assert v < 2**96
        v = utils.zpad(utils.int_to_big_endian(v), 12)
        pair = v + to
        assert len(pair) == 32
        args.append(pair)
    return args, value


class PaymentProcessor(object):

    # Gas price: 20 shannons, Homestead suggested gas price.
    GAS_PRICE = 20 * 10**9

    # Gas reservation for performing single batch payment.
    # TODO: Adjust this value later and add MAX_PAYMENTS limit.
    GAS_RESERVATION = 21000 + 1000 * 50000

    BANK_ADDR = "cfdc7367e9ece2588afe4f530a9adaa69d5eaedb".decode('hex')

    SENDOUT_TIMEOUT = 1 * 60
    SYNC_CHECK_INTERVAL = 10

    def __init__(self, client, privkey, faucet=False):
        self.__client = client
        self.__privkey = privkey
        self.__balance = None
        self.__deposit = None
        self.__reserved = 0
        self.__awaiting = []    # Awaiting individual payments
        self.__inprogress = {}  # Sent transactions.
        self.__last_sync_check = time.time()
        self.__sync = False
        self.__temp_sync = False
        self.__faucet = faucet
        self.__faucet_request_ttl = 0

        # Very simple sendout scheduler.
        # TODO: Maybe it should not be the part of this class
        # TODO: Allow seting timeout
        # TODO: Defer a call only if payments waiting
        scheduler = LoopingCall(self.run)
        scheduler.start(self.SENDOUT_TIMEOUT)

    def synchronized(self):
        """ Checks if the Ethereum node is in sync with the network."""

        if time.time() - self.__last_sync_check <= self.SYNC_CHECK_INTERVAL:
            # When checking again within 10 s return previous status.
            # This also handles geth issue where synchronization starts after
            # 10 s since the node was started.
            return self.__sync

        def check():
            peers = self.__client.get_peer_count()
            log.info("Peer count: {}".format(peers))
            if peers == 0:
                return False
            if self.__client.is_syncing():
                log.info("Node is syncing...")
                return False
            return True

        # Normally we should check the time of latest block, but Golem testnet
        # does not produce block regularly. The workaround is to wait for 2
        # confirmations.
        prev = self.__temp_sync
        # Remember current check as a temporary status.
        self.__temp_sync = check()
        # Mark as synchronized only if previous and current status are true.
        self.__sync = prev and self.__temp_sync
        log.info("Synchronized: {}".format(self.__sync))
        return self.__sync

    def balance(self, refresh=False):
        # FIXME: The balance must be actively monitored!
        if self.__balance is None or refresh:
            addr = keys.privtoaddr(self.__privkey)
            # TODO: Hack RPC client to allow using raw address.
            self.__balance = self.__client.get_balance('0x' + addr.encode('hex'))
            log.info("Balance: {}".format(self.__balance / denoms.ether))
        return self.__balance

    def deposit_balance(self, refresh=False):
        if self.__deposit is None or refresh:
            data = bank_contract.encode('balance', ())
            addr = keys.privtoaddr(self.__privkey)
            r = self.__client.call(_from='0x' + addr.encode('hex'),
                                   to='0x' + self.BANK_ADDR.encode('hex'),
                                   data=data.encode('hex'),
                                   block='pending')
            if r is None or r == '0x':
                self.__deposit = 0
            else:
                self.__deposit = int(r, 16)
            log.info("Deposit: {}".format(self.__deposit / denoms.ether))
        return self.__deposit

    def available_balance(self, refresh=False):
        fee_reservation = self.GAS_RESERVATION * self.GAS_PRICE
        available = self.balance(refresh) - self.__reserved - fee_reservation
        return max(available, 0)

    def add(self, payment):
        assert payment.status is PaymentStatus.awaiting
        value = payment.value
        assert type(value) in (int, long)
        balance = self.available_balance()
        log.info("Payment {:.6} to {:.6} ({:.6f})".format(
                 payment.subtask,
                 payment.payee.encode('hex'),
                 value / denoms.ether))
        if value > balance:
            log.warning("Low balance: {:.6f}".format(balance / denoms.ether))
            return False
        self.__awaiting.append(payment)
        self.__reserved += value
        log.info("Balance: {:.6f}, reserved {:.6f}".format(
                 balance / denoms.ether, self.__reserved / denoms.ether))
        return True

    def sendout(self):
        log.debug("Sendout ping")
        if not self.__awaiting:
            return

        payments = self.__awaiting  # FIXME: Should this list be synchronized?
        self.__awaiting = []
        addr = keys.privtoaddr(self.__privkey)  # TODO: Should be done once?
        nonce = self.__client.get_transaction_count('0x' + addr.encode('hex'))
        p, value = _encode_payments(payments)
        deposit = self.deposit_balance(refresh=True)
        # First use ether from deposit, so transfer only missing amount.
        transfer_value = max(value - deposit, 0)
        data = bank_contract.encode('transfer', [p])
        gas = 21000 + len(p) * 30000
        tx = Transaction(nonce, self.GAS_PRICE, gas, to=self.BANK_ADDR,
                         value=transfer_value, data=data)
        tx.sign(self.__privkey)
        h = tx.hash
        log.info("Batch payments: {:.6}, value: {:.6f}, transfer: {:.6f}"
                 .format(h.encode('hex'), value / denoms.ether,
                         transfer_value / denoms.ether))

        # Firstly write transaction hash to database. We need the hash to be
        # remembered before sending the transaction to the Ethereum node in
        # case communication with the node is interrupted and it will be not
        # known if the transaction has been sent or not.
        with Payment._meta.database.transaction():
            for payment in payments:
                assert payment.status == PaymentStatus.awaiting
                payment.status = PaymentStatus.sent
                payment.details['tx'] = h.encode('hex')
                payment.save()
                log.debug("- {} send to {} ({:.6f})".format(
                          payment.subtask,
                          payment.payee.encode('hex'),
                          payment.value / denoms.ether))

            tx_hash = self.__client.send(tx)
            assert tx_hash[2:].decode('hex') == h  # FIXME: Improve Client.

            self.__inprogress[h] = payments

    def monitor_progress(self):
        confirmed = []
        for h, payments in self.__inprogress.iteritems():
            hstr = h.encode('hex')
            log.info("Checking {:.6} tx [{}]".format(hstr, len(payments)))
            receipt = self.__client.get_transaction_receipt(hstr)
            if receipt:
                block_hash = receipt['blockHash'][2:]
                assert len(block_hash) == 2 * 32
                block_number = int(receipt['blockNumber'], 16)
                gas_used = int(receipt['gasUsed'], 16)
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
                        log.debug("- {:.6} confirmed fee {:.6f}".format(p.subtask,
                                  fee / denoms.ether))
                confirmed.append(h)
        for h in confirmed:
            # Reduced reserved balance here to minimize chance of double update.
            self.__reserved -= sum(p.value for p in self.__inprogress[h])
            assert self.__reserved >= 0
            # Delete in progress entry.
            del self.__inprogress[h]

    def get_ethers_from_faucet(self):
        if self.__faucet and self.balance(True) == 0:
            if self.__faucet_request_ttl > 0:
                # Waiting for transfer from the faucet
                self.__faucet_request_ttl -= 1
                return False
            value = 100
            log.info("Requesting {} ETH from Golem Faucet".format(value))
            addr = keys.privtoaddr(self.__privkey)
            Faucet.gimme_money(self.__client, addr, value * denoms.ether)
            self.__faucet_request_ttl = 10
            return False
        return True

    def run(self):
        if self.synchronized() and self.get_ethers_from_faucet():
            self.deposit_balance(refresh=True)
            self.monitor_progress()
            self.sendout()
