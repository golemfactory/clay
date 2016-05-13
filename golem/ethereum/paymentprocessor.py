import logging

from ethereum import abi, keys, utils
from ethereum.transactions import Transaction
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

    def __init__(self, client, privkey, faucet=False):
        self.__client = client
        self.__privkey = privkey
        self.__balance = None
        self.__reserved = 0
        self.__awaiting = []    # Awaiting individual payments
        self.__inprogress = {}  # Sent transactions.

        # Very simple sendout scheduler.
        # TODO: Maybe it should not be the part of this class
        # TODO: Allow seting timeout
        # TODO: Defer a call only if payments waiting
        scheduler = LoopingCall(self.run)
        scheduler.start(self.SENDOUT_TIMEOUT)

        if faucet and self.balance() == 0:
            value = 100
            log.info("Requesting {} ETH from Golem Faucet".format(value))
            addr = keys.privtoaddr(self.__privkey)
            Faucet.gimme_money(client, addr, value * 10**18)

    def balance(self, refresh=False):
        # FIXME: The balance must be actively monitored!
        if self.__balance is None or refresh:
            addr = keys.privtoaddr(self.__privkey)
            # TODO: Hack RPC client to allow using raw address.
            self.__balance = self.__client.get_balance(addr.encode('hex'))
            log.info("Balance: {}".format(self.__balance / float(10**18)))
        return self.__balance

    def available_balance(self, refresh=False):
        fee_reservation = self.GAS_RESERVATION * self.GAS_PRICE
        available = self.balance(refresh) - self.__reserved - fee_reservation
        return max(available, 0)

    def add(self, payment):
        assert payment.status is PaymentStatus.awaiting
        value = payment.value
        assert type(value) in (int, long)
        balance = self.available_balance()
        log.info("Payment to {} ({})".format(payment.payee, value))
        if value > balance:
            log.warning("Not enough money: {}".format(balance))
            return False
        self.__awaiting.append(payment)
        self.__reserved += value
        log.info("Balance: {}, reserved {}".format(balance, self.__reserved))
        return True

    def sendout(self):
        log.debug("Sendout ping")
        if not self.__awaiting:
            return

        payments = self.__awaiting  # FIXME: Should this list be synchronized?
        self.__awaiting = []
        addr = keys.privtoaddr(self.__privkey)  # TODO: Should be done once?
        nonce = self.__client.get_transaction_count(addr.encode('hex'))
        p, value = _encode_payments(payments)
        data = bank_contract.encode('transfer', [p])
        gas = 21000 + len(p) * 30000
        tx = Transaction(nonce, self.GAS_PRICE, gas, to=self.BANK_ADDR,
                         value=value, data=data)
        tx.sign(self.__privkey)
        h = tx.hash
        log.info("Batch payments: {}".format(h.encode('hex')))

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

            tx_hash = self.__client.send(tx)
            assert tx_hash[2:].decode('hex') == h  # FIXME: Improve Client.

            self.__inprogress[h] = payments

    def monitor_progress(self):
        confirmed = []
        for h, payments in self.__inprogress.iteritems():
            hstr = h.encode('hex')
            log.info("Checking {} transaction".format(hstr))
            info = self.__client.get_transaction_by_hash(hstr)
            assert info, "Transaction has been lost"
            if info['blockHash']:
                block_hash = info['blockHash'][2:]
                assert len(block_hash) == 2 * 32
                block_number = int(info['blockNumber'], 16)
                log.info("{}: block {} ({})".format(hstr, block_hash, block_number))
                with Payment._meta.database.transaction():
                    for p in payments:
                        p.status = PaymentStatus.confirmed
                        p.details['block_number'] = block_number
                        p.details['block_hash'] = block_hash
                        p.save()
                confirmed.append(h)
        for h in confirmed:
            del self.__inprogress[h]

    def run(self):
        self.sendout()
        self.monitor_progress()
