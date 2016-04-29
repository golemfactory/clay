from twisted.internet.task import LoopingCall

from golem.model import PaymentStatus

from .paymentprocessor import PaymentProcessor, log


class IncomingPayment(object):
    def __init__(self, payer, value):
        self.status = PaymentStatus.confirmed
        self.payer = payer
        self.value = value
        self.extra = {}  # For additional data.


class PaymentMonitor(object):
    def __init__(self, client, addr):
        self.__client = client
        self.__addr = addr
        self.__filter = None
        self.__payments = []

        scheduler = LoopingCall(self.get_incoming_payments)
        scheduler.start(10)  # FIXME: Use single scheduler for all payments.

    def get_incoming_payments(self):
        if not self.__filter:
            # solidity Transfer() log id
            # FIXME: Take it from contract ABI
            log_id = 'ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
            # Search for logs Transfer(..., my address)
            # TODO: We can safe some gas by not indexing "from" address
            bank_addr = PaymentProcessor.BANK_ADDR.encode('hex')
            topics = [log_id, None, self.__addr.encode('hex')]
            self.__filter = self.__client.new_filter(from_block='earliest',
                                                     to_block='latest',
                                                     address=bank_addr,
                                                     topics=topics)

        new_logs = self.__client.get_filter_changes(self.__filter)
        for l in new_logs:
            payer = l['topics'][1][26:].decode('hex')
            assert len(payer) == 20
            payee = l['topics'][2][26:].decode('hex')
            assert payee == self.__addr
            value = int(l['data'], 16)
            block_number = int(l['blockNumber'], 16)
            block_hash = l['blockHash'][2:].decode('hex')
            assert len(block_hash) == 32
            tx_hash = l['transactionHash'][2:].decode('hex')
            assert len(tx_hash) == 32
            payment = IncomingPayment(payer, value)
            payment.extra = {'block_number': block_number,
                             'block_hash': block_hash,
                             'tx_hash': tx_hash}
            self.__payments.append(payment)
            log.info("Incoming payment: {} -> ({} ETH)".format(
                     payer.encode('hex'), value / float(10**18)))

        return self.__payments
