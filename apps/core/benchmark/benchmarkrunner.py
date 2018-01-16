import abc
import logging

from apps.core.task.coretaskstate import TaskDefinition
from golem.task.localcomputer import LocalComputer
from golem.task.taskbase import Task

logger = logging.getLogger("apps.core")


class CoreBenchmark(metaclass=abc.ABCMeta):
    @property
    @abc.abstractmethod
    def normalization_constant(self) -> float:
        pass

    @property
    @abc.abstractmethod
    def task_definition(self) -> TaskDefinition:
        pass

    # argument is a list of files produced in computation (logs and outputs)
    @abc.abstractmethod
    def verify_result(self, result_data_path) -> bool:
        pass


class BenchmarkRunner(LocalComputer):
    RUNNER_WARNING = "Failed to compute benchmark"
    RUNNER_SUCCESS = "Benchmark computed successfully"



    def __init__(self, task: Task, root_path, success_callback, error_callback, benchmark: CoreBenchmark):
        def get_compute_task_def():
            return task.query_extra_data(10000).ctd

        super().__init__(root_path=root_path,
                         success_callback=success_callback,
                         error_callback=error_callback,
                         # ugly lambda, should think of something prettier
                         get_compute_task_def=get_compute_task_def,
                         check_mem=True,
                         comp_failed_warning=BenchmarkRunner.RUNNER_WARNING,
                         comp_success_message=BenchmarkRunner.RUNNER_SUCCESS,
                         resources=task.get_resources())
        # probably this could be done differently
        self.benchmark = benchmark

    def _get_task_thread(self, ctd):
        if not ctd['docker_images']:
            raise Exception("No docker container found")
        return super(BenchmarkRunner, self)._get_task_thread(ctd)

    def is_success(self, task_thread):
        if not task_thread.result:
            return False
        try:
            res, _ = task_thread.result
        except (ValueError, TypeError):
            return False
        if not res or ("data" not in res):
            return False
        if self.end_time is None or self.start_time is None:
            return False
        return self.benchmark.verify_result(res["data"])

    def computation_success(self, task_thread):
        res, _ = task_thread.result
        try:
            benchmark_value = self.benchmark.normalization_constant / self._get_time_spent()
            if benchmark_value < 0:
                raise ZeroDivisionError
        except ZeroDivisionError:
            benchmark_value = self.benchmark.normalization_constant / 1e-10
        self.success_callback(benchmark_value)
