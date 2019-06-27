from ..playbook import Playbook as NodeTestPlaybook
from ....test_config_base import NodeId


class Playbook(NodeTestPlaybook):
    def step_verify_deposit_balance_call(self):
        def on_success(result):
            if result['value'] and result['status'] and result['timelock']:
                print("Result correct %s" % result)
                self.next()
            else:
                print("Unexpected result: %s" % result)

        def on_error(error):
            self.fail(error)

        return self.call(NodeId.provider, 'pay.deposit_balance',
                         on_success=on_success, on_error=on_error)
