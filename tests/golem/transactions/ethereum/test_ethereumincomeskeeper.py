import mock
import uuid

from golem import testutils
from golem.transactions.ethereum.ethereumincomeskeeper \
    import EthereumIncomesKeeper


def get_some_id():
    return str(uuid.uuid4())


def get_receiver_id():
    return '0x0000000000000000000000007d577a597b2742b498cb5cf0c26cdcd726d39e6e'


class TestEthereumIncomesKeeper(testutils.DatabaseFixture, testutils.PEP8MixIn):
    PEP8_FILES = [
        'golem/transactions/ethereum/ethereumincomeskeeper.py',
    ]

    def setUp(self):
        super().setUp()
        self.sci = mock.Mock()
        self.eth_address = get_receiver_id()
        self.instance = EthereumIncomesKeeper(self.eth_address, self.sci)

    def test_start_stop(self):
        self.sci.subscribe_to_incoming_batch_transfers.assert_called_once_with(
            self.eth_address,
            0,
            self.instance._on_batch_event,
            self.instance.REQUIRED_CONFS,
        )

        block_number = 123
        self.sci.get_block_number.return_value = block_number
        self.instance.stop()

        self.sci.reset_mock()
        instance = EthereumIncomesKeeper(self.eth_address, self.sci)
        self.sci.subscribe_to_incoming_batch_transfers.assert_called_once_with(
            self.eth_address,
            block_number - (instance.REQUIRED_CONFS +
                            instance.BLOCK_NUMBER_BUFFER),
            instance._on_batch_event,
            instance.REQUIRED_CONFS,
        )
