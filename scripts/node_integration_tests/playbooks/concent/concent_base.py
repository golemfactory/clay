import queue
import typing

from scripts.node_integration_tests import helpers

from ..base import NodeTestPlaybook


class ConcentTestPlaybook(NodeTestPlaybook):
    def step_clear_requestor_output(self):
        helpers.clear_output(self.requestor_output_queue)
        self.next()

    def step_clear_provider_output(self):
        helpers.clear_output(self.provider_output_queue)
        self.next()

    def _step_is_concent_off(self, role):
        call_method = getattr(self, 'call_' + role)

        def on_success(result):
            if result is True:
                print("Concent unexpectedly already enabled for %s...", role)
            return self.next()

        return call_method('golem.concent.switch', on_success=on_success)

    def step_is_provider_concent_off(self):
        return self._step_is_concent_off('provider')

    def step_is_requestor_concent_off(self):
        return self._step_is_concent_off('requestor')

    def _step_enable_concent(self, role):
        call_method = getattr(self, 'call_' + role)

        def on_success(_):
            self.next()

        def on_error(result):
            print("Error enabling Concent for %s" % role)
            self.fail()

        return call_method(
            'golem.concent.switch.turn', 1,
            on_success=on_success, on_error=on_error,
        )

    def step_enable_provider_concent(self):
        return self._step_enable_concent('provider')

    def step_enable_requestor_concent(self):
        return self._step_enable_concent('requestor')

    def _step_ensure_concent_on(self, role):
        call_method = getattr(self, 'call_' + role)

        def on_success(result):
            if result is True:
                print("Enabled Concent for %s." % role)
                self.next()
            else:
                self.fail(
                    "Failed to enable Concent for %s... (result=%r)" % (
                        role, result
                    )
                )
            return self.next()

        return call_method('golem.concent.switch', on_success=on_success)

    def step_ensure_provider_concent_on(self):
        return self._step_ensure_concent_on('provider')

    def step_ensure_requestor_concent_on(self):
        return self._step_ensure_concent_on('requestor')

    @staticmethod
    def check_concent_logs(
            output_queue: queue.Queue,
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
        step_is_provider_concent_off,
        step_enable_provider_concent,
        step_ensure_provider_concent_on,

        step_is_requestor_concent_off,
        step_enable_requestor_concent,
        step_ensure_requestor_concent_on,

        step_clear_requestor_output,
        step_clear_provider_output,
    )
