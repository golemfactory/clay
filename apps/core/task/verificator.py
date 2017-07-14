import logging
import os

from enum import Enum

from golem.core.common import HandleKeyError

logger = logging.getLogger("apps.core")


def state_check_log_key_error(*args, **kwargs):
    logger.warning("This is not my subtask {}".format(args[1]))
    return SubtaskVerificationState.UNKNOWN


class SubtaskVerificationState(Enum):
    UNKNOWN = 0
    WAITING = 1
    PARTIALLY_VERIFIED = 2
    VERIFIED = 3
    WRONG_ANSWER = 4


class CoreVerificator(object):
    handle_key_error_for_state = HandleKeyError(state_check_log_key_error)

    def __init__(self, verification_options=None, advanced_verification=False):
        self.ver_states = {}
        self.advanced_verification = advanced_verification
        self.verification_options = verification_options

    def set_verification_options(self, verification_options):
        self.verification_options = verification_options
        if verification_options is None:
            self.advanced_verification = False
        else:
            self.advanced_verification = True

    def is_verified(self, subtask_id):
        return self.ver_states.get(subtask_id) == SubtaskVerificationState.VERIFIED

    @handle_key_error_for_state
    def get_verification_state(self, subtask_id):
        return self.ver_states[subtask_id]

    @handle_key_error_for_state
    def verify(self, subtask_id, subtask_info, tr_files, task):
        self._check_files(subtask_id, subtask_info, tr_files, task)
        return self.ver_states[subtask_id]

    def _check_files(self, subtask_id, subtask_info, tr_files, task):
        for tr_file in tr_files:
            if os.path.isfile(tr_file):
                self.ver_states[subtask_id] = SubtaskVerificationState.VERIFIED
                return
        self.ver_states[subtask_id] = SubtaskVerificationState.WRONG_ANSWER


