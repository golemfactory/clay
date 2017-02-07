from devp2p.crypto import privtopub
from ethereum import keys
from mock import patch, Mock

from golem.tools.testwithdatabase import TestWithDatabase
from golem.transactions.ethereum.ethereumtransactionsystem import EthereumTransactionSystem

PRIV_KEY = '\7' * 32


class TestEthereumTransactionSystem(TestWithDatabase):
    def test_init(self):
        e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        self.assertIsInstance(e, EthereumTransactionSystem)
        assert type(e.get_payment_address()) is str

    def test_invalid_private_key(self):
        with self.assertRaises(ValueError):
            EthereumTransactionSystem(self.tempdir, "not a private key")

    def test_wrong_address_in_pay_for_task(self):
        addr = keys.privtoaddr(PRIV_KEY)
        e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        assert e.get_payment_address() == '0x' + addr.encode('hex')
        e.pay_for_task("xyz", [])

    def test_get_balance(self):
        e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        assert e.get_balance() == (0, 0, 0)

    def test_stop(self):

        pkg = 'golem.ethereum.'

        def init(*args, **kwargs):
            return

        with patch(pkg + 'paymentprocessor.PaymentProcessor.start'), \
            patch(pkg + 'paymentprocessor.PaymentProcessor.stop'), \
            patch(pkg + 'paymentmonitor.PaymentMonitor.start'), \
            patch(pkg + 'paymentmonitor.PaymentMonitor.stop'), \
            patch(pkg + 'node.NodeProcess.start'), \
            patch(pkg + 'node.NodeProcess.stop'), \
            patch('web3.Web3.__init__', init), \
            patch('web3.providers.rpc.KeepAliveRPCProvider.__init__', init):

            e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)

            assert e._EthereumTransactionSystem__proc.start.called
            assert e._EthereumTransactionSystem__monitor.start.called
            assert e._EthereumTransactionSystem__eth_node.node.start.called

            e.stop()

            assert not e._EthereumTransactionSystem__proc.stop.called
            assert not e._EthereumTransactionSystem__monitor.stop.called
            assert e._EthereumTransactionSystem__eth_node.node.stop.called

            e._EthereumTransactionSystem__eth_node.node.stop.called = False
            e._EthereumTransactionSystem__proc._loopingCall.running = True
            e._EthereumTransactionSystem__monitor._loopingCall.running = True

            e.stop()

            assert e._EthereumTransactionSystem__proc.stop.called
            assert e._EthereumTransactionSystem__monitor.stop.called
            assert e._EthereumTransactionSystem__eth_node.node.stop.called
