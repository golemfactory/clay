import logging
import time

from golem.task.localcomputer import LocalComputer

logger = logging.getLogger("apps.core")


class BenchmarkRunner(LocalComputer):
    RUNNER_WARNING = "Failed to compute benchmark"
    RUNNER_SUCCESS = "Benchmark computed successfully"

    def __init__(self, task, root_path, success_callback, error_callback, benchmark):
        super(BenchmarkRunner, self).__init__(task,
                                              root_path,
                                              success_callback,
                                              error_callback,
                                              # ugly lambda, should think of something prettier
                                              lambda: task.query_extra_data(10000).ctd,
                                              True,
                                              BenchmarkRunner.RUNNER_WARNING,
                                              BenchmarkRunner.RUNNER_SUCCESS)
        # probably this could be done differently
        self.benchmark = benchmark

    def _get_task_thread(self, ctd):
        if not ctd.docker_images:
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
