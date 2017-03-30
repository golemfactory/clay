from __future__ import division

from ethereum.utils import denoms, zpad
from pydispatch import dispatcher

from golem.resource.client import async_run, AsyncRequest
from golem.transactions.service import Service
from golem.model import PaymentStatus

from .paymentprocessor import PaymentProcessor, log


class IncomingPayment(object):
    def __init__(self, payer, value):
        self.status = PaymentStatus.confirmed
        self.payer = payer
        self.value = value
        self.extra = {}  # For additional data.


class PaymentMonitor(Service):
    BANK_ADDR = "0x689ed42Ec0C3b3B799Dc5659725Bf536635F45d1"

    def __init__(self, client, addr):
        self.__client = client
        self.__addr = addr
        self.__filter = None
        self.__payments = []
        super(PaymentMonitor, self).__init__(30)

    def get_incoming_payments(self):
        """Return cached incoming payments fetch from blockchain."""
        return self.__payments

    def _run(self):
        async_run(AsyncRequest(self.process_incoming_payments))

    def process_incoming_payments(self):
        log.debug("process incoming payments")
        if not self.__filter:
            # solidity Transfer() log id
            # FIXME: Take it from contract ABI
            log_id = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
            # Search for logs Transfer(..., my address)
            # TODO: We can save some gas by not indexing "from" address
            topics = [log_id, None, '0x' + zpad(self.__addr, 32).encode('hex')]
            self.__filter = self.__client.new_filter(from_block='earliest',
                                                     to_block='latest',
                                                     address=self.BANK_ADDR,
                                                     topics=topics)

        new_logs = self.__client.get_filter_changes(self.__filter)
        if not new_logs:
            return self.__payments

        for l in new_logs:
            payer = l['topics'][1][26:].decode('hex')
            if len(payer) != 20:
                raise ValueError("Incorrect payer length: {}. Should be 20".format(len(payer)))
            payee = l['topics'][2][26:].decode('hex')
            if payee != self.__addr:
                raise ValueError("Payee should be: {}, but is: {}".format(self.__addr, payee))
            value = int(l['data'], 16)

            log.debug("BlockHash: {}; BlockNumber: {}".format(l['blockHash'], l['blockNumber']))
            block_number = l['blockNumber']
            block_hash = None
            if l['blockHash']:
                block_hash = l['blockHash'][2:].decode('hex')
                if len(block_hash) != 32:
                    raise ValueError("Incorrect block hash length: {} .Should be 32".format(len(block_hash)))
            tx_hash = l['transactionHash'][2:].decode('hex')
            if len(tx_hash) != 32:
                raise ValueError("Incorrect tx length: {}. Should be 32".format(len(tx_hash)))
            payment = IncomingPayment(payer, value)
            payment.extra = {'block_number': block_number,
                             'block_hash': block_hash,
                             'tx_hash': tx_hash}
            self.__payments.append(payment)
            dispatcher.send(signal='golem.monitor', event='income', addr=payer.encode('hex'), value=value)
            log.info("Incoming payment: {} -> ({} GNT)".format(
                payer.encode('hex'), value / denoms.ether))

        return self.__payments
