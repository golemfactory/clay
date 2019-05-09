from typing import Tuple

from golem.task.taskstate import SubtaskOp


class ProviderEfficacy:
    """
    Provider efficacy from Requestor perspective as proposed in
    https://docs.golem.network/About/img/Brass_Golem_Marketplace.pdf
    """
    _OPS = [
        SubtaskOp.FINISHED,
        SubtaskOp.TIMEOUT,
        SubtaskOp.FAILED,
        SubtaskOp.NOT_ACCEPTED,
    ]

    def __init__(self, s: float, t: float, f: float, r: float) -> None:
        self._vec: Tuple[float, ...] = (s, t, f, r)

    @property
    def vector(self) -> Tuple[float, ...]:
        return self._vec

    def update(self, op: SubtaskOp, psi: float = 0.9) -> None:
        if op not in self._OPS:
            return

        update_vec = [float(op == o) for o in self._OPS]
        it = map(lambda x, y: x * psi + y, self._vec, update_vec)

        self._vec = tuple(it)

    def serialize(self) -> str:
        return ', '.join(map(str, self._vec))

    @classmethod
    def deserialize(cls, value: str) -> 'ProviderEfficacy':
        values = tuple(map(float, value.split(',')))
        return ProviderEfficacy(*values)

    def __repr__(self):
        return f'{self.__class__.__name__}({self.serialize()})'
