from functools import partial
import typing

from scripts.node_integration_tests import helpers

from ...base import NodeTestPlaybook
from ...test_config_base import NodeId


class Playbook(NodeTestPlaybook):
    def step_wait_task_finished(self):
        verification_rejected = helpers.search_output(
            self.output_queues[NodeId.provider], '.*SubtaskResultsRejected.*'
        )

        if verification_rejected:
            self.fail(verification_rejected.group(0))
            return

        return super().step_wait_task_finished()

    steps: typing.Tuple = NodeTestPlaybook.initial_steps + (
        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        step_wait_task_finished,
        NodeTestPlaybook.step_verify_output,
        NodeTestPlaybook.step_get_subtasks,
        NodeTestPlaybook.step_verify_income,
    )
