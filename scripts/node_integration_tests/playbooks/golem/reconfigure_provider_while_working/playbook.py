import time
from functools import partial

from scripts.node_integration_tests import helpers
from ...test_config_base import NodeId
from ..task_api.playbook import Playbook as BasePlaybook


class Playbook(BasePlaybook):
    def wait_for_computing_task(self):
        def on_success(result):
            state = result['provider_state']
            print(f"provider state: {state}")
            if state['status'] == 'Computing':
                self.next()
            else:
                time.sleep(10)

        def on_error(_):
            print(f"failed getting provider stats")
            self.fail()
        return self.call(NodeId.provider, 'comp.tasks.stats',
                         on_success=on_success, on_error=on_error)

    def ui_stop(self, node_id: NodeId):
        def on_success(_):
            print(f"stopped {node_id.value}")
            self.next()

        def on_error(_):
            print(f"stopping {node_id.value} failed")
            self.fail()
        return self.call(node_id, 'ui.stop', on_success=on_success,
                         on_error=on_error)

    def change_config(self, node_id: NodeId):
        opts = {
            "node_name": "a new name",
        }

        def on_success(_):
            print(f"reconfigured {node_id.value}")
            time.sleep(10)  # give time for async operations to process
            self.next()

        def on_error(_):
            print(f"reconfiguring {node_id.value} failed")
            self.fail()

        return self.call(node_id, 'env.opts.update', opts,
                         on_success=on_success, on_error=on_error)

    def check_if_test_failed(self, node_id: NodeId):
        test_failed = bool(helpers.search_output(
            self.output_queues[node_id],
            ".*#### Integration test failed ####.*"))

        if test_failed:
            self.fail("found failure marker in log")

        print("no failure marker found in log")
        self.next()

    steps = BasePlaybook.initial_steps + (
        BasePlaybook.step_enable_app,
        BasePlaybook.step_create_task,
        BasePlaybook.step_get_task_id,
        BasePlaybook.step_get_task_status,
        wait_for_computing_task,
        partial(ui_stop, node_id=NodeId.provider),
        partial(change_config, node_id=NodeId.provider),
        partial(check_if_test_failed, node_id=NodeId.provider),
    )
