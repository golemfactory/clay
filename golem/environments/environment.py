import enum
import logging

from os import path

from apps.rendering.benchmark.minilight.src.minilight import make_perf_test

from golem.core.common import get_golem_path
from golem.environments.minperformancemultiplier import MinPerformanceMultiplier
from golem.model import Performance


class SupportStatus(object):
    def __init__(self, ok, desc=None) -> None:
        self.desc = desc or {}
        self._ok = ok

    def is_ok(self) -> bool:
        return self._ok

    def __bool__(self) -> bool:
        return self.is_ok()

    def __eq__(self, other) -> bool:
        return self.is_ok() == other.is_ok() and self.desc == other.desc

    def join(self, other) -> 'SupportStatus':
        desc = self.desc.copy()
        desc.update(other.desc)
        return SupportStatus(self.is_ok() and other.is_ok(), desc)

    @classmethod
    def ok(cls) -> 'SupportStatus':
        return cls(True)

    @classmethod
    def err(cls, desc) -> 'SupportStatus':
        return cls(False, desc)

    def __repr__(self) -> str:
        return '<SupportStatus %s (%r)>' % \
            ('ok' if self._ok else 'err', self.desc)


class UnsupportReason(enum.Enum):
    ENVIRONMENT_MISSING = 'environment_missing'
    ENVIRONMENT_UNSUPPORTED = 'environment_unsupported'
    ENVIRONMENT_NOT_ACCEPTING_TASKS = 'environment_not_accepting_tasks'
    ENVIRONMENT_NOT_SECURE = 'environment_not_secure'
    MAX_PRICE = 'max_price'
    APP_VERSION = 'app_version'
    DENY_LIST = 'deny_list'
    REQUESTOR_TRUST = 'requesting_trust'
    NETWORK_REQUEST = 'cannot_perform_network_request'
    MASK_MISMATCH = 'mask_mismatch'
    CONCENT_REQUIRED = 'concent_required'


class Environment():

    @classmethod
    def get_id(cls):
        """ Get Environment unique id
        :return str:
        """
        return "DEFAULT"

    def __init__(self):
        self.short_description = "Default environment for generic tasks" \
                                 " without any additional requirements."

        self.accept_tasks = False

    def check_support(self) -> SupportStatus:
        """ Check if this environment is supported on this machine
        :return SupportStatus:
        """
        return SupportStatus.ok()

    def is_accepted(self):
        """ Check if user wants to compute tasks from this environment
        :return bool:
        """
        return self.accept_tasks

    @classmethod
    def get_performance(cls):
        """ Return performance index associated with the environment. Return
        0.0 if performance is unknown
        :return float:
        """
        try:
            perf = Performance.get(Performance.environment_id == cls.get_id())
        except Performance.DoesNotExist:
            return 0.0
        return perf.value

    @classmethod
    def get_min_accepted_performance(cls) -> float:
        """ Return minimal accepted performance for the environment.
        :return float:
        """
        step: float = 300
        try:
            perf = Performance.get(Performance.environment_id == cls.get_id())
            step = perf.min_accepted_step
        except Performance.DoesNotExist:
            pass

        return step * MinPerformanceMultiplier.get()

    @classmethod
    def run_default_benchmark(cls, save=False):
        logger = logging.getLogger('golem.task.benchmarkmanager')
        logger.info('Running benchmark for %s', cls.get_id())
        test_file = path.join(get_golem_path(), 'apps', 'rendering',
                              'benchmark', 'minilight', 'cornellbox.ml.txt')
        performance = make_perf_test(test_file)
        logger.info('%s performance is %.2f', cls.get_id(), performance)
        if save:
            Performance.update_or_create(cls.get_id(), performance)
        return performance
