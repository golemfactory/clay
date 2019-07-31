from functools import partial
import typing

from ...base import NodeTestPlaybook
from ...test_config_base import NodeId


class Playbook(NodeTestPlaybook):

    steps: typing.Tuple = NodeTestPlaybook.initial_steps + (
        partial(NodeTestPlaybook.step_ensure_concent_off,
                node_id=NodeId.provider),
        partial(NodeTestPlaybook.step_enable_concent,
                node_id=NodeId.provider),
        partial(NodeTestPlaybook.step_ensure_concent_on,
                node_id=NodeId.provider),

        partial(NodeTestPlaybook.step_ensure_concent_off,
                node_id=NodeId.requestor),
        partial(NodeTestPlaybook.step_enable_concent,
                node_id=NodeId.requestor),
        partial(NodeTestPlaybook.step_ensure_concent_on,
                node_id=NodeId.requestor),

        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        NodeTestPlaybook.step_wait_task_finished,
        NodeTestPlaybook.step_verify_output,
        NodeTestPlaybook.step_get_subtasks,
        NodeTestPlaybook.step_verify_income,
    )
