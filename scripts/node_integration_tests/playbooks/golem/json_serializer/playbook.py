from functools import partial

from ...base import NodeTestPlaybook
from ...test_config_base import NodeId


class Playbook(NodeTestPlaybook):
    def step_check_bignum(self):
        def on_success(result):
            if result != (2**64 + 1337):
                self.fail()
                return
            print("transferring bigints works correctly")
            self.next()

        def on_error(error):
            print(f"Error: {error}")
            self.fail()

        return self.call(NodeId.requestor, 'test.bignum', on_success=on_success,
                         on_error=on_error)

    steps = (
        partial(NodeTestPlaybook.step_get_key, node_id=NodeId.requestor),
        step_check_bignum,
    ) + NodeTestPlaybook.steps
