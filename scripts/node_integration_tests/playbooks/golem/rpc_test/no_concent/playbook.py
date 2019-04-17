from ....base import NodeTestPlaybook


class Playbook(NodeTestPlaybook):
    def step_verify_deposit_balance_call(self):
        def on_success(_):
            self.success()

        def on_error(error):
            self.fail(error)

        return self.call_provider(
            'pay.deposit_balance', on_success=on_success, on_error=on_error)

    steps = (
        NodeTestPlaybook.step_get_provider_key,
        NodeTestPlaybook.step_get_requestor_key,
        NodeTestPlaybook.step_get_provider_network_info,
        NodeTestPlaybook.step_connect_nodes,
        NodeTestPlaybook.step_verify_peer_connection,
        step_verify_deposit_balance_call,
    )
