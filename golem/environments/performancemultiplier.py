from golem import model
from golem.model import GenericKeyValue


class PerformanceMultiplier:
    DB_KEY = 'performance_multiplier'

    @classmethod
    def get_percent(cls) -> float:
        """ Returns performance multiplier.
        :return float:
        """
        rows = GenericKeyValue.select(GenericKeyValue.value).where(
            GenericKeyValue.key == cls.DB_KEY)
        return float(rows.get().value) if rows.count() == 1 else 100

    @classmethod
    def set_percent(cls, percent: float):
        """ Sets performance multiplier."""
        if percent < 0 or percent > 1000:
            raise Exception(f'performance multiplier ({percent}) must be '
                            'within [0, 1000] inclusive.')

        with model.db.atomic():
            entry, _ = GenericKeyValue.get_or_create(key=cls.DB_KEY)
            entry.value = str(percent)
            entry.save()
