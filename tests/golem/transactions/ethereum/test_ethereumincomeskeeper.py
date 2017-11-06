import unittest.mock as mock
import random
import sys
import uuid

from golem.model import db
from golem import model
from golem import testutils
from golem.transactions.ethereum.ethereumincomeskeeper \
    import EthereumIncomesKeeper

from tests.golem.transactions.test_incomeskeeper import generate_some_id, \
    MAX_INT
from golem.network.p2p.node import Node
from golem.model import ExpectedIncome, Income, BigIntegerField


def get_some_id():
    return str(uuid.uuid4())


def get_receiver_id():
    return '0x0000000000000000000000007d577a597b2742b498cb5cf0c26cdcd726d39e6e'


class TestEthereumIncomesKeeper(testutils.DatabaseFixture, testutils.PEP8MixIn):
    PEP8_FILES = [
        'golem/transactions/ethereum/ethereumincomeskeeper.py',
    ]

    def setUp(self, ):
        super(TestEthereumIncomesKeeper, self).setUp()
        random.seed()
        payment_processor = mock.MagicMock()
        payment_processor.eth_address.return_value = get_receiver_id()
        payment_processor.is_synchronized.return_value = True
        self.instance = EthereumIncomesKeeper(payment_processor)

    @mock.patch('golem.transactions.incomeskeeper.IncomesKeeper.received')
    def test_received(self, super_received_mock):
        received_kwargs = {
            'sender_node_id': get_some_id(),
            'task_id': get_some_id(),
            'subtask_id': get_some_id(),
            'transaction_id': get_some_id(),
            'block_number': random.randint(0, int(MAX_INT / 2)),
            'value': random.randint(10, int(MAX_INT / 2)),
        }

        # Transaction not in blockchain
        self.instance.processor.get_logs.return_value = None
        self.instance.received(**received_kwargs)
        super_received_mock.assert_not_called()
        self.instance.processor.wait_until_synchronized.assert_not_called()

        self.instance.processor.is_synchronized.return_value = False
        self.instance.received(**received_kwargs)
        assert self.instance.processor.wait_until_synchronized.call_count == 1
        self.instance.processor.is_synchronized.return_value = True

        # Payment for someone else
        self.instance.processor.get_logs.return_value = [
            {
                'topics': [
                    EthereumIncomesKeeper.LOG_ID,
                    get_some_id(),  # sender
                    get_some_id(),  # receiver
                ],
                'data': hex(random.randint(1, sys.maxsize)),
            },
        ]
        self.instance.received(**received_kwargs)
        super_received_mock.assert_not_called()
        super_received_mock.reset_mock()

        # Payment for us but value to small
        self.instance.processor.get_logs.return_value.append({
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
        self.instance.processor.get_logs.return_value.append({
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
        self.instance.processor.get_logs.return_value.append({
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
            'subtask_id': 's1' + get_some_id()[:-2],
            'transaction_id': get_some_id(),
            'block_number': random.randint(0, int(MAX_INT / 2)),
            'value': MAX_INT,
        }
        db_value = BigIntegerField().db_value(received_kwargs['value'])

        self.instance.processor.get_logs.return_value = [{
            'topics': [
                EthereumIncomesKeeper.LOG_ID,
                get_some_id(),  # sender
                self.instance.processor.eth_address(),  # receiver
            ],
            'data': db_value
        }]

        self.instance.received(**received_kwargs)

        # check the the income is in db
        with db.atomic():
            self.assertEqual(
                1,
                model.Income.select().where(
                    model.Income.subtask == received_kwargs['subtask_id']
                ).count()
            )

            getincome = model.Income.get(
                sender_node=received_kwargs['sender_node_id'],
                task=received_kwargs['task_id'],
                subtask=received_kwargs['subtask_id'])
            self.assertEqual(getincome.value, received_kwargs['value'])
            self.assertEqual(getincome.transaction,
                             received_kwargs['transaction_id'])
            self.assertEqual(getincome.block_number,
                             received_kwargs['block_number'])

        # Try to use the same payment for another subtask
        received_kwargs['subtask_id'] = 's2' + get_some_id()[:-2]
        # Paranoid mode: Make sure subtask_id wasn't used before
        self.assertEqual(
            0,
            model.Income.select().where(
                model.Income.subtask == received_kwargs['subtask_id']
            ).count(),
            "Paranoid duplicated subtask check failed"
        )

        self.instance.received(**received_kwargs)
        self.assertEqual(
            0,
            model.Income.select().where(
                model.Income.subtask == received_kwargs['subtask_id']
            ).count()
        )

    def test_batched_payment(self):
        # ARRANGE
        sender_node_id = generate_some_id('sender_node_id')
        task_id = generate_some_id('task_id')
        subtask_ids = [generate_some_id('subtask_id'),
                       generate_some_id('subtask_id2')]
        node = Node()
        value = random.randint(MAX_INT, MAX_INT + 10)

        self.assertEqual(ExpectedIncome.select().count(), 0)
        for subtask_id in subtask_ids:
            self.instance.expect(
                sender_node_id=sender_node_id,
                task_id=task_id,
                subtask_id=subtask_id,
                p2p_node=node,
                value=value
            )
        self.assertEqual(ExpectedIncome.select().count(), 2)

        # Batched Payment with exact value
        db_value = BigIntegerField().db_value(2 * value)
        self.instance.processor.get_logs.return_value = [{
            'topics': [
                EthereumIncomesKeeper.LOG_ID,
                get_some_id(),  # sender
                self.instance.processor.eth_address(),  # receiver
            ],
            'data': db_value}]

        # ACT
        # inform about the payment for the first subtask
        transaction_id = get_some_id()
        block_number = random.randint(0, int(MAX_INT / 2))
        received_kwargs = {
            'sender_node_id': sender_node_id,
            'task_id': task_id,
            'subtask_id': subtask_ids[0],
            'transaction_id': transaction_id,
            'block_number': block_number,
            'value': value,
        }
        self.instance.received(**received_kwargs)

        # inform about the payment for the second subtask
        received_kwargs = {
            'sender_node_id': sender_node_id,
            'task_id': task_id,
            'subtask_id': subtask_ids[1],
            'transaction_id': transaction_id,
            'block_number': block_number,
            'value': value,
        }
        self.instance.received(**received_kwargs)

        # ASSERT
        self.assertEqual(Income.select().count(), 2)
        self.assertEqual(ExpectedIncome.select().count(), 0)
