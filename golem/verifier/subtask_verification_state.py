from enum import IntEnum


class SubtaskVerificationState(IntEnum):
    UNKNOWN_SUBTASK = 0
    WAITING = 1
    IN_PROGRESS = 2
    VERIFIED = 3
    WRONG_ANSWER = 4
    NOT_SURE = 5
    TIMEOUT = 6
