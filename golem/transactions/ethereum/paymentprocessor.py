
import logging
from enum import Enum

from ethereum import abi, keys, utils
from ethereum.transactions import Transaction

from golem.ethereum.contracts import BankOfDeposit


log = logging.getLogger("golem.pay")

bank_contract = abi.ContractTranslator(BankOfDeposit.ABI)


class Status(Enum):
    init = 1
    awaiting = 2
    sent = 3
    confirmed = 4


class OutgoingPayment(object):

    def __init__(self, to, value):
        self.status = Status.init
        self.to = to
        self.value = value
        self.extra = {}  # For additional data.


def _encode_payments(payments):
    paymap = {}
    for p in payments:
        if p.to in paymap:
            paymap[p.to] += p.value
        else:
            paymap[p.to] = p.value

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

    def __init__(self, client, privkey):
        self.__client = client
        self.__privkey = privkey
        self.__balance = None
        self.__reserved = 0
        self.__awaiting = []    # Awaiting individual payments
        self.__inprogress = {}  # Sent transactions.

    def available_balance(self, refresh=False):
        if self.__balance is None or refresh:
            addr = keys.privtoaddr(self.__privkey)
            # TODO: Hack RPC client to allow using raw address.
            self.__balance = self.__client.get_balance(addr.encode('hex'))
        fee_reservation = self.GAS_RESERVATION * self.GAS_PRICE
        available = self.__balance - self.__reserved - fee_reservation
        return max(available, 0)

    def add(self, payment):
        assert payment.status is Status.init
        if payment.value > self.available_balance():
            return False
        self.__awaiting.append(payment)
        self.__reserved += payment.value
        payment.status = Status.awaiting
        return True

    def sendout(self):
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
        for payment in payments:
            assert payment.status == Status.awaiting
            payment.status = Status.sent
            payment.extra['tx'] = h
        try:
            tx_hash = self.__client.send(tx)
            assert tx_hash[2:].decode('hex') == h  # FIXME: Improve Client.
        except:
            log.exception("Problem with sending transaction. Reverting.")
            # In case of any problems revert payments status.
            for payment in payments:
                payment.status = Status.awaiting
                del payment.extra['tx']
            self.__awaiting = payments
            raise

        self.__inprogress[h] = payments
