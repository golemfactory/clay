import unittest
from unittest import mock

from golem.task.server.verification import VerificationMixin


class Verifier(VerificationMixin):
    pass


class TestGetPaymentComputer(unittest.TestCase):

    def setUp(self) -> None:
        self.market_legacy = mock.Mock()
        self.market_task_api = mock.Mock()
        self.apps = {
            'app_id': mock.Mock(market_strategy=self.market_task_api)
        }
        tasks = {
            'legacy_task_id': mock.Mock(
                REQUESTOR_MARKET_STRATEGY=self.market_legacy,
                header=mock.Mock(subtask_timeout=3600),
                subtask_price=10 ** 18,
            )
        }
        task_api_tasks = {
            'task_api_task_id': mock.Mock(
                app_id='app_id',
                subtask_timeout=1800,
            )
        }
        task_api_subtasks = {
            'subtask_id': mock.Mock(price=10 ** 17),
        }

        am = mock.Mock(app=self.apps.get)
        tm = mock.Mock(tasks=tasks)
        rtm = mock.Mock(
            get_requested_task=task_api_tasks.get,
            get_requested_task_subtask=mock.Mock(
                side_effect=(
                    lambda t, s: task_api_subtasks.get(s)
                    if t in task_api_tasks else None
                ),
            )
        )

        self.verifier = Verifier()
        self.verifier.app_manager = am
        self.verifier.task_manager = tm
        self.verifier.requested_task_manager = rtm
        self.get = self.verifier._get_payment_computer

    def test_legacy(self):
        self.get(
            task_id='legacy_task_id',
            subtask_id='subtask_id')

        self.assertFalse(self.market_task_api.get_payment_computer.called)
        self.market_legacy.get_payment_computer.assert_called_with(
            'subtask_id',
            subtask_timeout=3600,
            subtask_price=10 ** 18)

    def test_task_api(self):
        self.get(
            task_id='task_api_task_id',
            subtask_id='subtask_id')

        self.assertFalse(self.market_legacy.get_payment_computer.called)
        self.market_task_api.get_payment_computer.assert_called_with(
            'subtask_id',
            subtask_timeout=1800,
            subtask_price=10 ** 17)

    def test_task_id_invalid(self):
        with self.assertRaises(RuntimeError) as ctx:
            self.get(task_id='UNKNOWN', subtask_id='subtask_id')
            self.assertIn(str(ctx.exception), "unknown task")

    def test_subtask_id_invalid(self):
        with self.assertRaises(RuntimeError) as ctx:
            self.get(task_id='task_api_task_id', subtask_id='UNKNOWN')
            self.assertIn(str(ctx.exception), "unknown subtask")

    def test_app_id_invalid(self):
        self.apps.clear()
        with self.assertRaises(RuntimeError) as ctx:
            self.get(task_id='task_api_task_id', subtask_id='subtask_id')
            self.assertIn(str(ctx.exception), "unknown app")
