from golem import model
from golem.model import GenericKeyValue
from golem.rpc import utils as rpc_utils


class MinPerformanceMultiplier:
    DB_KEY = 'minimal_performance_multiplier'
    MIN = 0
    MAX = 100
    DEFAULT = MIN

    @rpc_utils.expose('performance.multiplier')
    @classmethod
    def get(cls) -> float:
        """ Returns performance multiplier. Default is 0.
        :return float:
        """
        rows = GenericKeyValue.select(GenericKeyValue.value).where(
            GenericKeyValue.key == cls.DB_KEY)
        return float(rows.get().value) if rows.count() == 1 else cls.DEFAULT

    @rpc_utils.expose('performance.multiplier.update')
    @classmethod
    def set(cls, value: float):
        """ Sets performance multiplier."""
        if float(value) < cls.MIN or float(value) > cls.MAX:
            raise Exception(f'minimal performance multiplier ({value}) must be '
                            f'within [{cls.MIN}, {cls.MAX}] inclusive.')

        with model.db.atomic():
            entry, _ = GenericKeyValue.get_or_create(key=cls.DB_KEY)
            entry.value = str(value)
            entry.save()
