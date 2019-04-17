from enum import Enum


class SubtaskVerificationState(Enum):
    UNKNOWN_SUBTASK = 0
    WAITING = 1
    IN_PROGRESS = 2
    VERIFIED = 3
    WRONG_ANSWER = 4
    NOT_SURE = 5
    TIMEOUT = 6
