from typing import List

from golem.task.taskstate import SubtaskOp


class ProviderEfficacy:

    _OPS = [
        SubtaskOp.FINISHED,
        SubtaskOp.TIMEOUT,
        SubtaskOp.FAILED,
        SubtaskOp.NOT_ACCEPTED,
    ]

    def __init__(self, *vec: float) -> None:
        self._vec: List[float] = vec

    @property
    def vector(self) -> List[float]:
        return self._vec[:]

    def update(self, op: SubtaskOp, psi: float = 0.9) -> None:
        if op not in self._OPS:
            return

        update_vec = [float(op == o) for o in self._OPS]
        it = map(lambda x, y: x * psi + y, self._vec, update_vec)

        self._vec = list(it)