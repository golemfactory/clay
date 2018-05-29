from copy import copy
import logging
import os
from typing import Union

from apps.core.benchmark.benchmarkrunner import BenchmarkRunner
from apps.core.task.coretaskstate import TaskDesc
from golem.environments.environment import Environment

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

    @staticmethod
    def get_saved_benchmarks_ids():
        query = Performance.select(Performance.environment_id)
        ids = set(benchmark.environment_id for benchmark in query)
        return ids

    def benchmarks_needed(self):
        if self.benchmarks:
            ids = self.get_saved_benchmarks_ids()
            return not set(self.benchmarks.keys() | {'DEFAULT'}).issubset(ids)
        return False

    def run_benchmark(self, benchmark, task_builder, env_id, success=None,
                      error=None):
        logger.info('Running benchmark for %s', env_id)

        from golem.network.p2p.node import Node

        def success_callback(performance):
            logger.info('%s performance is %.2f', env_id, performance)
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
        builder = task_builder(Node(),
                               task_state.definition,
                               self.dir_manager)
        t = Task.build_task(builder)
        br = BenchmarkRunner(t, self.task_server.client.datadir,
                             success_callback, error_callback,
                             benchmark)
        br.run()

    def run_all_benchmarks(self, success=None, error=None):
        logger.info('Running all benchmarks with num_cores=%d',
                    self.task_server.client.config_desc.num_cores)

        if Environment.get_id() not in self.get_saved_benchmarks_ids():
            Environment.run_default_benchmark(num_cores=1, save=True)

        benchmarks_copy = copy(self.benchmarks)
        self.run_benchmarks(benchmarks_copy, success, error)

    def run_benchmarks(self, benchmarks, success=None, error=None):
        env_id, (benchmark, builder_class) = benchmarks.popitem()

        def on_success(performance):
            if benchmarks:
                self.run_benchmarks(benchmarks, success, error)
            else:
                if success:
                    success(performance)

        self.run_benchmark(benchmark, builder_class, env_id, on_success, error)

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
            raise Exception("Unknown environment: {}".format(env_id))
