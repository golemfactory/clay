from unittest.mock import MagicMock

from golem.task.taskkeeper import TaskHeaderKeeper
from golem.task.server.resources import TaskResourcesMixin
from golem.testutils import TestWithClient


class TestTaskResourcesMixin(TestWithClient):
    def setUp(self):
        super().setUp()
        self.server = TaskResourcesMixin()
        self.server.task_manager = self.client.task_manager
        self.server.client = self.client
        self.server.task_keeper = TaskHeaderKeeper(
            environments_manager=self.client.environments_manager,
            node=self.client.node,
            min_price=0
        )

    def test_request_resource(self):
        assert self.server.request_resource("task_id1", "subtask_id", [])
