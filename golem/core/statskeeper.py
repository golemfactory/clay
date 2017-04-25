import logging
from threading import Lock

from golem.core.common import HandleAttributeError
from golem.model import Stats

logger = logging.getLogger(__name__)


def log_attr_error(*args, **kwargs):
    logger.warning("Unknown stats %r", args[1])


class StatsKeeper(object):

    handle_attribute_error = HandleAttributeError(log_attr_error)

    def __init__(self, stat_class, default_value=''):
        self._lock = Lock()
        self.session_stats = stat_class()
        self.global_stats = stat_class()
        self.default = default_value
        self.init_global_stats()

    @handle_attribute_error
    def init_global_stats(self):
        for stat in vars(self.global_stats).keys():
            with self._lock:
                val = self._retrieve_stat(stat)
                if val:
                    setattr(self.global_stats, stat, val)

    def get_stats(self, name):
        stats = self._get_stat(name)
        if stats is None:
            stats = (None, None)
        return stats

    def _retrieve_stat(self, name):
        try:
            stat, _ = Stats.get_or_create(name=name, defaults={'value': self.default})
            return stat.value
        except Exception:
            logger.warning("Cannot retrieve %r from  database:", name, exc_info=True)

    @handle_attribute_error
    def _get_stat(self, name):
        return getattr(self.session_stats, name), getattr(self.global_stats, name)


class IntStatsKeeper(StatsKeeper):

    def __init__(self, stat_class):
        super(IntStatsKeeper, self).__init__(stat_class, '0')

    @StatsKeeper.handle_attribute_error
    def increase_stat(self, stat_name, increment=1):
        with self._lock:
            val = getattr(self.session_stats, stat_name)
            setattr(self.session_stats, stat_name, val + 1)
            global_val = self._retrieve_stat(stat_name)
            if global_val is not None:
                setattr(self.global_stats, stat_name, global_val + increment)
                try:
                    Stats.update(value=u"{}".format(global_val+increment)).where(Stats.name == stat_name).execute()
                except Exception as err:
                    logger.error("Exception occured while updating stat %r: %r", stat_name, err)

    def _retrieve_stat(self, name):
        try:
            stat_val = StatsKeeper._retrieve_stat(self, name)
            return int(stat_val)
        except (ValueError, TypeError) as err:
            logger.warning("Wrong stat %r format: %r", name, err)
