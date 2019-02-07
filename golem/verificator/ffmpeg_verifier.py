import logging
import os

from golem.verificator import CoreVerifier
from golem.verificator.verifier import SubtaskVerificationState

logger = logging.getLogger("apps.ffmpeg")


class FFmpegVerifier(CoreVerifier):
    def __init__(self, verification_data):
        super(FFmpegVerifier, self).__init__()

    # def _verify_with_reference(self, verification_data):
    #     # TODO
    #     return self.verification_completed()

    def simple_verification(self, verification_data):
        verdict = False
        self.state = SubtaskVerificationState.WRONG_ANSWER
        try:
            results = self._get_result_info(verification_data)
            verdict = self._check_results(results)
            self.state = SubtaskVerificationState.VERIFIED
        except KeyError:
            self.message = "Missing results in verification_data"
        except RuntimeError:
            self.message = "No results from provider"
        except FileNotFoundError:
            self.results.clear()
            self.message = "No proper task result found"

        return verdict

    @staticmethod
    def _get_result_info(verification_data):
        return verification_data["results"]

    def _check_results(self, results):
        if not results:
            raise RuntimeError

        for result in results:
            self._check_file_existence(result)
            self.results.append(result)

        return True

    @staticmethod
    def _check_file_existence(path):
        if not os.path.exists(path):
            raise FileNotFoundError
        return True

