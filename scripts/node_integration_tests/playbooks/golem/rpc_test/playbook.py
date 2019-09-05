from functools import partial

from ...base import NodeTestPlaybook
from ...test_config_base import NodeId


class Playbook(NodeTestPlaybook):
    def step_verify_deposit_balance_call(self):
        def on_success(_):
            self.next()

        def on_error(error):
            self.fail(error)

        return self.call(NodeId.provider, 'pay.deposit_balance',
                         on_success=on_success, on_error=on_error)

    steps = (
        partial(NodeTestPlaybook.step_get_key, node_id=NodeId.provider),
        partial(NodeTestPlaybook.step_get_key, node_id=NodeId.requestor),
        partial(NodeTestPlaybook.step_get_network_info,
                node_id=NodeId.provider),
        partial(NodeTestPlaybook.step_get_network_info,
                node_id=NodeId.requestor),
        partial(NodeTestPlaybook.step_connect, node_id=NodeId.requestor,
                target_node=NodeId.provider),
        partial(NodeTestPlaybook.step_verify_connection,
                node_id=NodeId.requestor, target_node=NodeId.provider),
        step_verify_deposit_balance_call,
    )
