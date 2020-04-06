from functools import partial

from ...base import NodeTestPlaybook
from .test_config import NodeId


class Playbook(NodeTestPlaybook):

    initial_steps  = (
        partial(NodeTestPlaybook.step_get_key, node_id=NodeId.requestor),
        partial(NodeTestPlaybook.step_get_address, node_id=NodeId.requestor),
        partial(NodeTestPlaybook.step_get_key, node_id=NodeId.provider),
        partial(NodeTestPlaybook.step_get_address, node_id=NodeId.provider),
        partial(NodeTestPlaybook.step_get_key, node_id=NodeId.provider2),
        partial(NodeTestPlaybook.step_get_address, node_id=NodeId.provider2),

        partial(NodeTestPlaybook.step_configure, node_id=NodeId.requestor),
        partial(NodeTestPlaybook.step_configure, node_id=NodeId.provider),
        partial(NodeTestPlaybook.step_configure, node_id=NodeId.provider2),

        partial(NodeTestPlaybook.step_get_network_info,
                node_id=NodeId.requestor),
        partial(NodeTestPlaybook.step_get_network_info,
                node_id=NodeId.provider),
        partial(NodeTestPlaybook.step_get_network_info,
                node_id=NodeId.provider2),

        partial(NodeTestPlaybook.step_connect, node_id=NodeId.provider,
                target_node=NodeId.requestor),
        partial(NodeTestPlaybook.step_verify_connection,
                node_id=NodeId.requestor, target_node=NodeId.provider),

        partial(NodeTestPlaybook.step_connect, node_id=NodeId.provider2,
                target_node=NodeId.requestor),
        partial(NodeTestPlaybook.step_verify_connection,
                node_id=NodeId.requestor, target_node=NodeId.provider2),

        partial(NodeTestPlaybook.step_wait_for_gnt, node_id=NodeId.requestor),

        NodeTestPlaybook.step_get_known_tasks,
    )

    steps = initial_steps + (

        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,

        NodeTestPlaybook.step_wait_task_finished,
        NodeTestPlaybook.step_get_subtasks,

        partial(NodeTestPlaybook.step_verify_income, node_id=NodeId.provider),
        partial(NodeTestPlaybook.step_verify_income, node_id=NodeId.provider2),
    )
