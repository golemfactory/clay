from abc import ABC, abstractmethod

from os import path
from typing import List

from apps.rendering.benchmark.minilight.src.minilight import make_perf_test

from golem.core.common import get_golem_path
from golem.model import Performance
from golem.task.requirement import Support


# pylint: disable=too-many-instance-attributes
class Environment(ABC):
    DEFAULT_ID = "DEFAULT"

    @classmethod
    def create(cls, **kwargs):
        """ Create instance of environment with string arguments passed
        in kwargs. This method is used for creating environments from
        config file's data.
        :param kwargs:
        :return:
        """
        proper_kwargs = cls.parse_init_args(**kwargs)
        return cls(**proper_kwargs)

    @classmethod
    def parse_init_args(cls, **kwargs):
        return kwargs

    # pylint: disable=no-self-use
    def get_id(self):
        """ Get Environment unique id
        :return str:
        """
        return Environment.DEFAULT_ID

    # pylint: disable=unused-argument
    def __init__(self, **kwargs):
        self.software = []  # list of software that should be installed
        self.caps = []  # list of hardware requirements
        self.supports: List[Support] = []
        self.short_description = "Default environment for generic tasks" \
                                 " without any additional requirements."

        self.long_description = ""
        self.accept_tasks = False
        # Check if tasks can define the source code
        self.allow_custom_source_code = False
        self.default_program_file = None
        self.source_code_required = False

    def _check_software(self):
        """ Check if required software is installed on this machine
        :return bool:
        """
        if self.source_code_required and not self.allow_custom_source_code:
            return self.default_program_file and \
                   path.isfile(self.default_program_file)

        return True

    # pylint: disable=no-self-use
    def _check_caps(self):
        """ Check if required hardware is available on this machine.
        :return bool:
        """
        return True

    def check_support(self) -> bool:
        """ Check if this environment is supported on this machine
        :return bool:
        """
        return bool(self._check_software() and self._check_caps())

    def is_accepted(self):
        """ Check if user wants to compute tasks from this environment
        :return bool:
        """
        return self.accept_tasks

    def satisfies_requirements(self, requirements) -> bool:
        return all(self._satisfies_requirement(r) for r in requirements)

    def _satisfies_requirement(self, requirement) -> bool:
        return any(support.satisfies(requirement)
                   for support in self.get_supports())

    # pylint: disable=no-self-use
    def get_supports(self):
        return []

    def get_performance(self):
        return Environment.get_performance_for_id(self.get_id())

    @staticmethod
    def get_performance_for_id(env_id):
        """ Return performance index associated with the environment. Return
        0.0 if performance is unknown
        :return float:
        """
        try:
            perf = Performance.get(Performance.environment_id == env_id)
            return perf.value
        except Performance.DoesNotExist:
            return 0.0

    # pylint: disable=too-many-arguments
    @abstractmethod
    def get_task_thread(self, taskcomputer, subtask_id, short_desc,
                        src_code, extra_data, task_timeout,
                        working_dir, resource_dir, temp_dir, **kwargs):
        pass

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
        if self.default_program_file and path.isfile(self.default_program_file):
            with open(self.default_program_file) as f:
                return f.read()

    @abstractmethod
    def get_benchmark(self):
        """
        Should return a pair of benchmark and benchmark task builder.
        :return:
        """
        pass

    @staticmethod
    def run_default_benchmark(num_cores=1, save=False,
                              env_id=DEFAULT_ID):
        test_file = path.join(get_golem_path(), 'apps', 'rendering',
                              'benchmark', 'minilight', 'cornellbox.ml.txt')
        estimated_performance = make_perf_test(test_file, num_cores=1)
        if save:
            Performance.update_or_create(env_id,
                                         estimated_performance)
        return estimated_performance
