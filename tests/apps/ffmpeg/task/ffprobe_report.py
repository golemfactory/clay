from typing import Any, Union


class FuzzyDuration:
    def __init__(self, duration: Union[float, int], tolerance: float) -> None:
        assert tolerance >= 0

        self._duration = duration
        self._tolerance = tolerance

    @property
    def duration(self) -> Any:
        return self._duration

    @property
    def tolerance(self) -> float:
        return self._tolerance

    def __eq__(self, other):
        if not isinstance(other, FuzzyDuration):
            return self._duration == other

        # We treat both fuzzy values as closed intervals:
        # [value - tolerance, value + tolerance]
        # If the intervals overlap at at least one point, we have a match.
        return abs(self.duration - other.duration) <= \
               self.tolerance + other.tolerance

    def __str__(self):
        if self._tolerance == 0:
            return f'{self._duration}'

        return f'{self._duration}[+/-{self._tolerance}]'

    def __repr__(self):
        return f'FuzzyDuration({self._duration}, {self._tolerance})'


class FuzzyInt:
    def __init__(self, value: int, tolerance_percent: int) -> None:
        assert tolerance_percent >= 0

        self._value = value
        self._tolerance_percent = tolerance_percent

    @property
    def value(self) -> int:
        return self._value

    @property
    def tolerance_percent(self) -> int:
        return self._tolerance_percent

    def __eq__(self, other):
        if not isinstance(other, FuzzyInt):
            return self._value == other

        tolerance = (
            abs(self.tolerance_percent * self.value) +
            abs(other.tolerance_percent * other.value)
        ) / 100
        return abs(self.value - other.value) <= tolerance

    def __str__(self):
        if self.tolerance_percent == 0:
            return f'{self._value}'

        return f'{self._value}[+/-{self.tolerance_percent}%]'

    def __repr__(self):
        return f'FuzzyInt({self._value}, {self.tolerance_percent})'
