import unittest
from unittest import mock

from golem.task.server.verification import VerificationMixin


class TestGetMarketStrategy(unittest.TestCase):

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
            get_requested_subtask=mock.Mock(
                side_effect=(
                    lambda s: task_api_subtasks.get(s)
                ),
            )
        )

        self.verifier = VerificationMixin()
        self.verifier.app_manager = am
        self.verifier.task_manager = tm
        self.verifier.requested_task_manager = rtm
        self.get = self.verifier._get_market_strategy

    def test_legacy(self):
        market = self.get(
            task_id='legacy_task_id',
            subtask_id='subtask_id')

        assert market is self.market_legacy

    def test_task_api(self):
        market = self.get(
            task_id='task_api_task_id',
            subtask_id='subtask_id')

        assert market is self.market_task_api

    def test_task_id_invalid(self):
        with self.assertRaisesRegex(RuntimeError, "unknown task"):
            self.get(task_id='UNKNOWN', subtask_id='subtask_id')

    def test_subtask_id_invalid(self):
        with self.assertRaisesRegex(RuntimeError, "unknown subtask"):
            self.get(task_id='task_api_task_id', subtask_id='UNKNOWN')

    def test_app_id_invalid(self):
        self.apps.clear()
        with self.assertRaisesRegex(RuntimeError, "unknown app"):
            self.get(task_id='task_api_task_id', subtask_id='subtask_id')
