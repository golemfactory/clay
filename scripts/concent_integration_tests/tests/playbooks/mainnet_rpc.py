from scripts.concent_integration_tests.rpc.client import (
    call_provider
)
from golem.config.environments import set_environment
from scripts.concent_integration_tests.tests.playbooks.base import NodeTestPlaybook


set_environment('mainnet', 'disabled')


class MainnetRPCTest(NodeTestPlaybook):
    provider_node_script = 'provider/mainnet'
    requestor_node_script = 'requestor/mainnet'

    def step_verify_deposit_balance_call(self):
        def on_success(_):
            self.success()

        def on_error(error):
            self.fail(error)

        call_provider(
            'pay.deposit_balance', on_success=on_success, on_error=on_error)

    steps = (
        NodeTestPlaybook.step_get_provider_key,
        NodeTestPlaybook.step_get_requestor_key,
        NodeTestPlaybook.step_get_provider_network_info,
        NodeTestPlaybook.step_connect_nodes,
        NodeTestPlaybook.step_verify_peer_connection,
        step_verify_deposit_balance_call,
    )
