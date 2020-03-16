import copy
from functools import partial
import tempfile
import time
import typing

from scripts.node_integration_tests import helpers

from ...base import NodeTestPlaybook
from ...test_config_base import NodeId

if typing.TYPE_CHECKING:
    from ...test_config_base import TestConfigBase


class Playbook(NodeTestPlaybook):
    def __init__(self, config: 'TestConfigBase') -> None:
        super().__init__(config)
        self.task_id2: typing.Optional[str] = None

    def step_get_task_id2(self, node_id: NodeId = NodeId.requestor):

        def on_success(result):
            task_id = self._identify_new_task_id(
                set(map(lambda r: r['id'], result)),
                self.known_tasks.union({self.task_id})
            )
            if task_id:
                self.task_id2 = task_id
                self.next()

        return self.call(node_id, 'comp.tasks', on_success=on_success)

    def step_wait_task_finished2(self, node_id: NodeId = NodeId.requestor):
        return self.step_wait_task_finished(
            node_id=node_id,
            task_id=self.task_id2
        )

    steps: typing.Tuple = NodeTestPlaybook.initial_steps + (
        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_create_task,
        step_get_task_id2,
        NodeTestPlaybook.step_wait_task_finished,
        step_wait_task_finished2,
    )
