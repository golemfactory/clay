from ..base import NodeTestPlaybook


class RPCTest(NodeTestPlaybook):
    provider_node_script = 'provider/debug'
    requestor_node_script = 'requestor/debug'

    def step_verify_deposit_balance_call(self):
        def on_success(result):
            if result['value'] and result['status'] and result['timelock']:
                print("Result correct %s" % result)
                self.success()
            else:
                print("Unexpected result: %s" % result)

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


class NoConcentRPCTest(NodeTestPlaybook):
    provider_node_script = 'provider/no_concent'
    requestor_node_script = 'requestor/no_concent'

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


class MainnetRPCTest(NoConcentRPCTest):
    provider_node_script = 'provider/mainnet'
    requestor_node_script = 'requestor/mainnet'
