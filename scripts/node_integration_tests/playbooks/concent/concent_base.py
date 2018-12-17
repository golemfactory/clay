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

    @staticmethod
    def check_concent_logs(
            output_queue,
            additional_fail_triggers: typing.Optional[list] = None,
            awaited_messages: typing.Optional[list] = None
    ) -> (typing.Optional[bool], typing.Optional[typing.Match]):
        """

        :param output_queue: the provider or requestor standard output queue
        :param additional_fail_triggers: any additional phrases that should be
                                         treated as (Concent) failures
        :param awaited_messages: class names of awaited Concent messages
        :return:
        """

        awaited_messages = awaited_messages or []

        concent_fail_triggers = [
            'Concent service exception',
            'Concent request failed',
            'Problem interpreting',
        ] + additional_fail_triggers or []

        log_match_pattern = \
            '.*' + '.*|.*'.join(
                concent_fail_triggers + (awaited_messages or [])
            ) + '.*'

        log_match = helpers.search_output(
            output_queue,
            log_match_pattern,
        )

        if log_match:
            match = log_match.group(0)
            if any([t in match for t in concent_fail_triggers]):
                return False, log_match
            if any([t in match and 'Concent Message received' in match
                    for t in awaited_messages]):
                return True, log_match

        return None, None

    initial_steps = NodeTestPlaybook.initial_steps + (
        step_clear_requestor_output,
        step_clear_provider_output,
    )
