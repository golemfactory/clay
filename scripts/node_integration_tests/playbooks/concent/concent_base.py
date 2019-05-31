from functools import partial
import typing

from scripts.node_integration_tests import helpers

from ..base import NodeTestPlaybook
from ..test_config_base import NodeId, TestConfigBase

if typing.TYPE_CHECKING:
    import queue


class ConcentTestPlaybook(NodeTestPlaybook):
    def __init__(self, config: 'TestConfigBase') -> None:
        super().__init__(config)
        self.retry_limit = 256

    def step_clear_output(self, node_id: NodeId):
        helpers.clear_output(self.output_queues[node_id])
        self.next()

    def step_check_is_concent_off(self, node_id: NodeId):
        def on_success(result):
            if result is True:
                print(f"Concent unexpectedly already enabled for"
                      " {node_id.value}...")
            self.next()

        return self.call(node_id, 'golem.concent.switch', on_success=on_success)

    def step_enable_concent(self, node_id: NodeId):
        def on_success(_):
            self.next()

        def on_error(result):
            print(f"Error enabling Concent for {node_id.value}")
            self.fail()

        return self.call(
            node_id,
            'golem.concent.switch.turn', 1,
            on_success=on_success, on_error=on_error,
        )

    def step_ensure_concent_on(self, node_id: NodeId):
        def on_success(result):
            if result is True:
                print(f"Enabled Concent for {node_id.value}.")
                self.next()
            else:
                self.fail(
                    "Failed to enable Concent for %s... (result=%r)" % (
                        node_id.value, result
                    )
                )
            self.next()

        return self.call(node_id, 'golem.concent.switch', on_success=on_success)

    @staticmethod
    def check_concent_logs(
            output_queue: 'queue.Queue',
            outgoing: bool = False,
            additional_fail_triggers: typing.Optional[list] = None,
            awaited_messages: typing.Optional[list] = None
    ) -> typing.Tuple[typing.Optional[bool], typing.Optional[typing.Match]]:
        """
        Process the golem node's log queue to look for names of expected
        messages, while at the same time checking if the logs don't contain
        any indication of Golem<->Concent communication failure.

        :param output_queue: the provider or requestor standard output queue
        :param outgoing: if `True` we're waiting for an outgoing message
                         (one that the node should send to Concent),
                         otherwise, when `False`, we're waiting for a message
                         from the Concent
        :param additional_fail_triggers: any additional phrases that should be
                                         treated as (Concent) failures
        :param awaited_messages: class names of awaited Concent messages
        :return: a tuple where the first value contains the result of the check
                 with `None` meaning that no patters were found yet,
                 `True` means successful detection of the message pattern
        """

        awaited_messages = awaited_messages or []

        concent_fail_triggers = [
            'Concent service exception',
            'Concent request failed',
            'Problem interpreting',
        ] + (additional_fail_triggers or [])

        log_match_pattern = \
            '.*' + '.*|.*'.join(
                concent_fail_triggers + (awaited_messages or [])
            ) + '.*'

        log_match = helpers.search_output(
            output_queue,
            log_match_pattern,
        )

        direction_trigger = (
            'send_to_concent' if outgoing else 'Concent Message received'
        )

        if log_match:
            match = log_match.group(0)
            if any([t in match for t in concent_fail_triggers]):
                return False, log_match
            if any([t in match
                    and direction_trigger in match
                    for t in awaited_messages]):
                return True, log_match

        return None, None

    initial_steps = NodeTestPlaybook.initial_steps + (
        partial(step_check_is_concent_off, node_id=NodeId.provider),
        partial(step_enable_concent, node_id=NodeId.provider),
        partial(step_ensure_concent_on, node_id=NodeId.provider),

        partial(step_check_is_concent_off, node_id=NodeId.requestor),
        partial(step_enable_concent, node_id=NodeId.requestor),
        partial(step_ensure_concent_on, node_id=NodeId.requestor),

        partial(step_clear_output, node_id=NodeId.requestor),
        partial(step_clear_output, node_id=NodeId.provider),
    )
