from functools import partial
import typing

from ...base import NodeTestPlaybook
from ...test_config_base import NodeId


class Playbook(NodeTestPlaybook):
    def step_ensure_concent_required(self, node_id: NodeId, is_on: bool):
        def on_success(result):
            if result is is_on:
                print(f"Concent is {'' if is_on else 'not '}required "
                      f"for {node_id.value} as expected.")
                self.next()
            else:
                self.fail(f"Concent unexpectedly "
                          f"{'not ' if is_on else ''}required "
                          f"for {node_id.value}... (result={result})")

        return self.call(
            node_id,
            'golem.concent.required_as_provider', on_success=on_success
        )

    def step_turn_concent_required(self, node_id: NodeId, on: bool):
        def on_success(_):
            self.next()

        def on_error(_):
            print(f"Error {'enabling' if on else 'disabling'} "
                  f"Concent for {node_id.value}")
            self.fail()

        return self.call(
            node_id,
            'golem.concent.required_as_provider.turn', on,
            on_success=on_success, on_error=on_error,
        )

    steps: typing.Tuple = NodeTestPlaybook.initial_steps + (
        # enable Concent for the provider

        partial(NodeTestPlaybook.step_ensure_concent_off,
                node_id=NodeId.provider),
        partial(NodeTestPlaybook.step_enable_concent,
                node_id=NodeId.provider),
        partial(NodeTestPlaybook.step_ensure_concent_on,
                node_id=NodeId.provider),
        partial(step_ensure_concent_required,
                node_id=NodeId.provider, is_on=True),

        # ensure Concent is disabled for the requestor

        partial(NodeTestPlaybook.step_ensure_concent_off,
                node_id=NodeId.requestor),

        # the task should time out

        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        NodeTestPlaybook.step_wait_task_timeout,

        partial(step_turn_concent_required,
                node_id=NodeId.provider, on=False),
        partial(step_ensure_concent_required,
                node_id=NodeId.provider, is_on=False),

        # the second task should now finish correctly

        NodeTestPlaybook.step_get_known_tasks,
        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        NodeTestPlaybook.step_wait_task_finished,
        NodeTestPlaybook.step_verify_output,
    )
