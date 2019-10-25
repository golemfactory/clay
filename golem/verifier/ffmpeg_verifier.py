import logging

from golem.verifier import CoreVerifier
from golem.verifier.core_verifier import SubtaskVerificationState

logger = logging.getLogger(__name__)


class FFmpegVerifier(CoreVerifier):
    def __init__(self, verification_data):
        super(FFmpegVerifier, self).__init__(verification_data)
        self.results = verification_data['results']
        self.state = SubtaskVerificationState.WAITING

    def simple_verification(self):
        verdict = super().simple_verification()

        # TODO more verification

        self.state = SubtaskVerificationState.VERIFIED if verdict \
            else SubtaskVerificationState.WRONG_ANSWER

        return verdict
