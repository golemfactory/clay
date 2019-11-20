import enum
import logging

from golem.environments.minperformancemultiplier import MinPerformanceMultiplier
from golem.envs import BenchmarkResult
from golem.envs.docker.benchmark.cpu.minilight import make_perf_test
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

    @property
    def err_reason(self):
        try:
            return list(self.desc.keys())[0]
        except (IndexError, AttributeError):
            return None

    def __repr__(self) -> str:
        return '<SupportStatus %s (%r)>' % \
            ('ok' if self._ok else 'err', self.desc)


class UnsupportReason(enum.Enum):
    ENVIRONMENT_MISSING = 'environment_missing'
    ENVIRONMENT_UNSUPPORTED = 'environment_unsupported'
    ENVIRONMENT_NOT_ACCEPTING_TASKS = 'environment_not_accepting_tasks'
    ENVIRONMENT_NOT_SECURE = 'environment_not_secure'
    ENVIRONMENT_MISCONFIGURED = 'environment_misconfigured'
    MAX_PRICE = 'max_price'
    APP_VERSION = 'app_version'
    DENY_LIST = 'deny_list'
    REQUESTOR_TRUST = 'requesting_trust'
    NETWORK_REQUEST = 'cannot_perform_network_request'
    MASK_MISMATCH = 'mask_mismatch'
    CONCENT_REQUIRED = 'concent_required'


class Environment():

    @classmethod
    def get_id(cls) -> str:
        """ Get Environment unique id """
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

    @classmethod
    def is_single_core(cls) -> bool:
        """ Returns true if task runs on single cpu core """
        return False

    def is_accepted(self) -> bool:
        """ Check if user wants to compute tasks from this environment """
        return self.accept_tasks

    @classmethod
    def get_benchmark_result(cls) -> BenchmarkResult:
        """ Return benchmark result associated with the environment. Return
        0 as performance and usage if benchmark hasn't been run yet.
        :return BenchmarkResult:
        """
        try:
            perf = Performance.get(Performance.environment_id == cls.get_id())
        except Performance.DoesNotExist:
            return BenchmarkResult()

        return BenchmarkResult.from_performance(perf)

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
    def run_default_benchmark(cls, save=False) -> BenchmarkResult:
        logger = logging.getLogger('golem.task.benchmarkmanager')
        logger.info('Running benchmark for %s', cls.get_id())
        performance = make_perf_test()
        logger.info('%s performance is %.2f', cls.get_id(), performance)

        if save:
            Performance.update_or_create(
                cls.get_id(), performance, Performance.DEFAULT_CPU_USAGE)

        return BenchmarkResult(performance, Performance.DEFAULT_CPU_USAGE)
