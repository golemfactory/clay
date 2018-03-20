import enum

from os import path

from apps.rendering.benchmark.minilight.src.minilight import make_perf_test

from golem.core.common import get_golem_path
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
    MAX_PRICE = 'max_price'
    APP_VERSION = 'app_version'
    DENY_LIST = 'deny_list'
    REQUESTOR_TRUST = 'requesting_trust'
    NETWORK_REQUEST = 'cannot_perform_network_request'


class Environment():

    @classmethod
    def get_id(cls):
        """ Get Environment unique id
        :return str:
        """
        return "DEFAULT"

    def __init__(self):
        self.software = []  # list of software that should be installed
        self.caps = []  # list of hardware requirements
        self.short_description = "Default environment for generic tasks" \
                                 " without any additional requirements."

        self.long_description = ""
        self.accept_tasks = False
        # Check if tasks can define the source code
        self.allow_custom_main_program_file = False
        self.main_program_file = None

    def check_software(self):
        """ Check if required software is installed on this machine
        :return bool:
        """
        if not self.allow_custom_main_program_file:
            return self.main_program_file and \
                path.isfile(self.main_program_file)

        return True

    def check_caps(self):
        """ Check if required hardware is available on this machine
        :return bool:
        """
        return True

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

    def description(self):
        """ Return long description of this environment
        :return str:
        """
        desc = self.short_description + "\n"
        if self.caps or self.software:
            desc += "REQUIREMENTS\n\n"
            if self.caps:
                desc += "CAPS:\n"
                for c in self.caps:
                    desc += "\t* " + c + "\n"
                desc += "\n"
            if self.software:
                desc += "SOFTWARE:\n"
                for s in self.software:
                    desc += "\t * " + s + "\n"
                desc += "\n"
        if self.long_description:
            desc += "Additional informations:\n" + self.long_description
        return desc

    def get_source_code(self):
        if self.main_program_file and path.isfile(self.main_program_file):
            with open(self.main_program_file) as f:
                return f.read()

    @classmethod
    def run_default_benchmark(cls, num_cores=1, save=False):
        test_file = path.join(get_golem_path(), 'apps', 'rendering',
                              'benchmark', 'minilight', 'cornellbox.ml.txt')
        estimated_performance = make_perf_test(test_file, num_cores=1)
        if save:
            Performance.update_or_create(cls.get_id(), estimated_performance)
        return estimated_performance
