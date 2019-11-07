from enum import Enum

TaskId = str
SubtaskId = str


class ComputationType(Enum):
    TEST = 'test'
    BENCHMARK = 'benchmark'
    SUBTASK = 'subtask'
    VERIFICATION = 'verification'
