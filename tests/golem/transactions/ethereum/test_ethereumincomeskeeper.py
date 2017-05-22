import mock
import random
import sys
import uuid

from golem import model
from golem import testutils
from golem.transactions.ethereum.ethereumincomeskeeper\
    import EthereumIncomesKeeper


def get_some_id():
    return str(uuid.uuid4())


class TestEthereumIncomesKeeper(testutils.DatabaseFixture, testutils.PEP8MixIn):
    PEP8_FILES = [
        'golem/transactions/ethereum/ethereumincomeskeeper.py',
    ]

    def setUp(self):
        super(TestEthereumIncomesKeeper, self).setUp()
        random.seed()
        self.instance = EthereumIncomesKeeper()
        self.instance.processor = mock.MagicMock()
        self.instance.processor.eth_address.return_value = get_some_id()
        self.instance.eth_node = mock.MagicMock()

    @mock.patch('golem.transactions.incomeskeeper.IncomesKeeper.received')
    def test_received(self, super_received_mock):
        received_kwargs = {
            'sender_node_id': get_some_id(),
            'task_id': get_some_id(),
            'subtask_id': get_some_id(),
            'transaction_id': get_some_id(),
            'block_number': random.randint(0, sys.maxint),
            'value': random.randint(10, sys.maxint),
        }
        # Not in blockchain
        self.instance.received(**received_kwargs)
        super_received_mock.assert_not_called()

        # Payment for someone else
        self.instance.eth_node.get_logs.return_value = [
            {
                'topics': [
                    EthereumIncomesKeeper.LOG_ID,
                    get_some_id(),  # sender
                    get_some_id(),  # receiver
                ],
                'data': hex(random.randint(1, sys.maxint)),
            },
        ]
        self.instance.received(**received_kwargs)
        super_received_mock.assert_not_called()
        super_received_mock.reset_mock()

        # Payment for us but value to small
        self.instance.eth_node.get_logs.return_value.append({
            'topics': [
                EthereumIncomesKeeper.LOG_ID,
                get_some_id(),  # sender
                self.instance.processor.eth_address(),  # receiver
            ],
            'data': hex(received_kwargs['value'] - 1),
        })
        self.instance.received(**received_kwargs)
        super_received_mock.assert_not_called()
        super_received_mock.reset_mock()

        # Payment with exact value
        self.instance.eth_node.get_logs.return_value.append({
            'topics': [
                EthereumIncomesKeeper.LOG_ID,
                get_some_id(),  # sender
                self.instance.processor.eth_address(),  # receiver
            ],
            'data': hex(1),
        })
        self.instance.received(**received_kwargs)
        super_received_mock.assert_called_once_with(**received_kwargs)
        super_received_mock.reset_mock()

        # Payment with higher value
        self.instance.eth_node.get_logs.return_value.append({
            'topics': [
                EthereumIncomesKeeper.LOG_ID,
                get_some_id(),  # sender
                self.instance.processor.eth_address(),  # receiver
            ],
            'data': hex(1),
        })
        self.instance.received(**received_kwargs)
        super_received_mock.assert_called_once_with(**received_kwargs)
        super_received_mock.reset_mock()

    def test_received_double_spending(self):
        received_kwargs = {
            'sender_node_id': get_some_id(),
            'task_id': get_some_id(),
            'subtask_id': 's1' + get_some_id(),
            'transaction_id': get_some_id(),
            'block_number': random.randint(0, sys.maxint),
            'value': random.randint(10, 2**10),
        }

        self.instance.eth_node.get_logs.return_value = [
            {
                'topics': [
                    EthereumIncomesKeeper.LOG_ID,
                    get_some_id(),  # sender
                    self.instance.processor.eth_address(),  # receiver
                ],
                'data': hex(received_kwargs['value']),
            },
        ]

        self.instance.received(**received_kwargs)
        self.assertEquals(
            1,
            model.Income.select().where(model.Income.subtask == received_kwargs['subtask_id'])
            .count()
        )

        # Try to use the same payment for another subtask
        received_kwargs['subtask_id'] = 's2' + get_some_id()
        self.instance.received(**received_kwargs)
        self.assertEquals(
            0,
            model.Income.select().where(model.Income.subtask == received_kwargs['subtask_id'])
            .count()
        )
