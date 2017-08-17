from mock import patch, MagicMock


from golem import testutils
from golem.tools.assertlogs import LogTestCase
from golem.tools.testwithdatabase import TestWithDatabase
from golem.transactions.ethereum.ethereumtransactionsystem import (
    EthereumTransactionSystem
)

PRIV_KEY = '07' * 32


class TestEthereumTransactionSystem(TestWithDatabase, LogTestCase,
                                    testutils.PEP8MixIn):
    PEP8_FILES = ['golem/transactions/ethereum/ethereumtransactionsystem.py', ]

    def test_init(self):
        e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        self.assertIsInstance(e, EthereumTransactionSystem)
        assert type(e.get_payment_address()) is str

    def test_invalid_private_key(self):
        with self.assertRaises(ValueError):
            EthereumTransactionSystem(self.tempdir, "not a private key")

    import mock
    @mock.patch('golem.transactions.ethereum.ethereumtransactionsystem.EthereumTransactionSystem.get_payment_address', new_callable=mock.PropertyMock)
    def test_invalid_eth_adress_construction(self, mock_get_payment_address):
        mock_get_payment_address().return_value = None

        with self.assertRaisesRegexp(ValueError, "Invalid Ethereum address constructed"):
            EthereumTransactionSystem(self.tempdir, PRIV_KEY)


    @patch('golem.ethereum.paymentprocessor.PaymentProcessor.start')
    @patch('golem.transactions.ethereum.ethereumtransactionsystem.sleep')
    def test_sync(self, sleep, *_ ):
        switch_value = [True]

        def false():
            return False

        def switch(*_):
            switch_value[0] = not switch_value[0]
            return not switch_value[0]

        def error(*_):
            raise Exception

        e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)

        sleep.call_count = 0
        with patch('golem.ethereum.paymentprocessor.PaymentProcessor.synchronized', side_effect=false):
            e.sync()
            assert sleep.call_count == 1

        sleep.call_count = 0
        with patch('golem.ethereum.paymentprocessor.PaymentProcessor.synchronized', side_effect=switch):
            e.sync()
            assert sleep.call_count == 2

        sleep.call_count = 0
        with patch('golem.ethereum.paymentprocessor.PaymentProcessor.synchronized', side_effect=error):
            e.sync()
            assert sleep.call_count == 0


    def test_get_balance(self):
        e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        assert e.get_balance() == (None, None, None)


    import mock
    @mock.patch('golem.transactions.service.Service.running', new_callable=mock.PropertyMock)
    def test_stop(self, mock_is_service_running):
        mock_is_service_running.return_value = True

        pkg = 'golem.ethereum.'

        def init(self, *args, **kwargs):
            self.rpcport = 65001
            self._NodeProcess__ps = None
            self.web3 = MagicMock()


        with patch(pkg + 'paymentprocessor.PaymentProcessor.start'), \
                patch('twisted.internet.task.LoopingCall.stop'), \
                patch(pkg + 'client.Client._kill_node'), \
                patch(pkg + 'node.NodeProcess.start'), \
                patch(pkg + 'node.NodeProcess.__init__', init), \
                patch('web3.providers.rpc.HTTPProvider.__init__', init):

            e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)

            assert e.incomes_keeper.processor._PaymentProcessor__client.node.start.called
            assert e.incomes_keeper.processor.start.called

            assert not e.incomes_keeper.processor._PaymentProcessor__client._kill_node.called
            assert not e.incomes_keeper.processor._loopingCall.stop.called

            mock_is_service_running.return_value = False
            with self.assertRaisesRegexp(RuntimeError, "service not started"):
                e.stop()

            assert not e.incomes_keeper.processor._PaymentProcessor__client._kill_node.called
            assert not e.incomes_keeper.processor._loopingCall.stop.called

            mock_is_service_running.return_value = True
            e.stop()

            assert e.incomes_keeper.processor._PaymentProcessor__client._kill_node.called
            assert e.incomes_keeper.processor._loopingCall.stop.called

