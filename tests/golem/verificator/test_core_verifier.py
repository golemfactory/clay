from datetime import datetime

import mock
from twisted.internet import defer
from twisted.trial import unittest

from golem.testutils import TempDirFixture
from golem.verificator.constants import SubtaskVerificationState
from golem.verificator.core_verifier import CoreVerifier


class TestCoreVerifier(unittest.SynchronousTestCase, TempDirFixture):

    def setUp(self):
        super().setUp()

        self.subtask_info = {'subtask_id': 5}
        files = self.additional_dir_content([1])
        self.verification_data = {"results": files}

    def test_start_verification_sets_status_verified_if_data_correct(self):
        def _is_status_correct(*_args, **_kwargs):
            return defer.succeed(
                core_verifier.state == SubtaskVerificationState.VERIFIED)

        core_verifier = CoreVerifier()
        core_verifier.subtask_info = self.subtask_info
        self.finished = core_verifier.start_verification(self.verification_data)
        self.finished.addCallback(_is_status_correct)
        self.assertTrue(self.successResultOf(self.finished))

    def test_start_verification_sets_status_wrong_answer_if_data_incorrect(
            self):
        with mock.patch.object(CoreVerifier, '_verify_result',
                               return_value=False):
            core_verifier = CoreVerifier()
            core_verifier.subtask_info = self.subtask_info
            self.finished = core_verifier.start_verification(
                self.verification_data)

            def _is_status_correct(*_args, **_kwargs):
                return defer.succeed(
                    core_verifier.state == SubtaskVerificationState.WRONG_ANSWER
                )

            self.finished.addCallback(_is_status_correct)
            self.assertTrue(self.successResultOf(self.finished))


class TestSimpleVerifier(TempDirFixture):

    def test_simple_verification(self):
        core_verifier = CoreVerifier()
        verification_data = dict()
        verification_data["results"] = []
        verification_data["subtask_info"] = "2432423"
        core_verifier.simple_verification(verification_data)
        assert core_verifier.state == SubtaskVerificationState.WRONG_ANSWER

        files = self.additional_dir_content([3])
        verification_data["results"] = files
        core_verifier.simple_verification(verification_data)
        assert core_verifier.state == SubtaskVerificationState.VERIFIED

        verification_data["results"] = [files[0]]
        core_verifier.simple_verification(verification_data)
        assert core_verifier.state == SubtaskVerificationState.VERIFIED

        verification_data["results"] = ["not a file"]
        core_verifier.simple_verification(verification_data)
        assert core_verifier.state == SubtaskVerificationState.WRONG_ANSWER

    @staticmethod
    def test_task_timeout():  # TODO: fix it
        subtask_id = 'abcde'

        def callback(*args, **kwargs):
            time = datetime.utcnow()

            assert kwargs['subtask_id'] == subtask_id
            assert kwargs['verdict'] == SubtaskVerificationState.TIMEOUT
            assert kwargs['result']['time_started'] == time
            assert kwargs['result']['time_ended'] == time

        sv = CoreVerifier()
        sv.callback = callback
        sv.task_timeout(subtask_id)
