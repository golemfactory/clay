from copy import copy
import logging
import os
from typing import Union

from apps.core.benchmark.benchmarkrunner import BenchmarkRunner
from apps.core.task.coretaskstate import TaskDesc

from golem.model import Performance
from golem.resource.dirmanager import DirManager
from golem.task.taskbase import Task
from golem.task.taskstate import TaskStatus

logger = logging.getLogger(__name__)


class BenchmarkManager(object):
    def __init__(self, node_name, task_server, root_path, benchmarks=None):
        self.benchmarks = benchmarks
        self.node_name = node_name
        self.task_server = task_server
        self.dir_manager = DirManager(root_path)

    def benchmarks_needed(self):
        if self.benchmarks:
            query = Performance.select(Performance.environment_id)
            data = set(benchmark.environment_id for benchmark in query)
            return not set(self.benchmarks.keys()).issubset(data)
        return False

    def run_benchmark(self, benchmark, task_builder, env_id, success=None,
                      error=None):

        def success_callback(performance):
            Performance.update_or_create(env_id, performance)
            if success:
                success(performance)

        def error_callback(err: Union[str, Exception]):
            logger.error("Unable to run %s benchmark: %s", env_id, str(err))
            if error:
                if isinstance(err, str):
                    err = Exception(err)
                error(err)

        task_state = TaskDesc()
        task_state.status = TaskStatus.notStarted
        task_state.definition = benchmark.task_definition
        self._validate_task_state(task_state)
        builder = task_builder(self.node_name, task_state.definition,
                               self.task_server.client.datadir,
                               self.dir_manager)
        t = Task.build_task(builder)
        br = BenchmarkRunner(t, self.task_server.client.datadir,
                             success_callback, error_callback,
                             benchmark)
        br.run()

    def run_all_benchmarks(self):
        benchmarks_copy = copy(self.benchmarks)
        self.run_benchmarks(benchmarks_copy)

    def run_benchmarks(self, benchmarks):
        # Next benchmark ran only if previous completed successfully
        if not benchmarks:
            return
        env_id, (benchmark, builder_class) = benchmarks.popitem()
        self.run_benchmark(benchmark, builder_class, env_id,
                           lambda _: self.run_benchmarks(benchmarks))

    def _validate_task_state(self, task_state):
        td = task_state.definition
        if not os.path.exists(td.main_program_file):
            logger.error("Main program file does not exist: {}".format(
                td.main_program_file))
            return False
        return True

    def run_benchmark_for_env_id(self, env_id, callback, errback):
        benchmark_data = self.benchmarks.get(env_id)
        if benchmark_data:
            self.run_benchmark(benchmark_data[0], benchmark_data[1],
                               env_id, callback, errback)
        else:
            raise Exception("Unkown environment: {}".format(env_id))
