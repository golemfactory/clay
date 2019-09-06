from copy import copy
import logging
from threading import Thread
from typing import Union

from apps.core.benchmark.benchmarkrunner import BenchmarkRunner
from apps.core.task.coretaskstate import TaskDesc
from golem.core.threads import callback_wrapper
from golem.environments.environment import Environment as DefaultEnvironment

from golem.model import Performance
from golem.resource.dirmanager import DirManager
from golem.task.taskstate import TaskStatus

logger = logging.getLogger(__name__)


class BenchmarkManager(object):
    def __init__(self, node_name, task_server, root_path, benchmarks=None):
        self.node_name = node_name
        self.task_server = task_server
        self.dir_manager = DirManager(root_path)
        self.benchmarks = benchmarks

    @staticmethod
    def get_saved_benchmarks_ids():
        query = Performance.select(Performance.environment_id)
        ids = set(benchmark.environment_id for benchmark in query)
        return ids

    def benchmarks_needed(self):
        if self.benchmarks:
            ids = self.get_saved_benchmarks_ids()
            return not set(self.benchmarks.keys() |
                           {DefaultEnvironment.get_id()}).issubset(ids)
        return False

    def run_benchmark(self, benchmark, task_builder, env_id, success=None,
                      error=None):
        logger.info('Running benchmark for %s', env_id)

        from golem_messages.datastructures.p2p import Node

        def success_callback(result: Performance):
            logger.info('%s benchmark finished. performance=%.2f, cpu_usage=%d',
                        env_id, result.value, result.cpu_usage)
            result.upsert()
            if success:
                success(result.value)

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
        builder = task_builder(Node(node_name=self.node_name),
                               task_state.definition,
                               self.dir_manager)
        task = builder.build()
        task.initialize(builder.dir_manager)

        br = BenchmarkRunner(
            task=task,
            root_path=self.dir_manager.root_path,
            success_callback=success_callback,
            error_callback=error_callback,
            benchmark=benchmark,
            env_id=env_id
        )
        br.run()

    def run_all_benchmarks(self, success=None, error=None):
        logger.info('Running all benchmarks with num_cores=%r',
                    self.task_server.client.config_desc.num_cores)

        def run_non_default_benchmarks(_performance=None):
            self.run_benchmarks(copy(self.benchmarks), success, error)

        if DefaultEnvironment.get_id() not in self.get_saved_benchmarks_ids():
            # run once in lifetime, since it's for single CPU core
            self.run_default_benchmark(run_non_default_benchmarks, error)
        else:
            run_non_default_benchmarks()

    def run_benchmarks(self, benchmarks, success=None, error=None):
        if not benchmarks:
            if success:
                success(None)
            return

        env_id, (benchmark, builder_class) = benchmarks.popitem()

        def recurse(_):
            self.run_benchmarks(benchmarks, success, error)

        self.run_benchmark(benchmark, builder_class, env_id, recurse, error)

    @staticmethod
    def _validate_task_state(task_state):
        return True

    def run_benchmark_for_env_id(self, env_id, callback, errback):
        if env_id == DefaultEnvironment.get_id():
            self.run_default_benchmark(callback, errback)
        else:
            benchmark_data = self.benchmarks.get(env_id)
            if benchmark_data:
                self.run_benchmark(benchmark_data[0], benchmark_data[1],
                                   env_id, callback, errback)
            else:
                raise Exception("Unknown environment: {}".format(env_id))

    @staticmethod
    def run_default_benchmark(callback, errback):
        kwargs = {'func': DefaultEnvironment.run_default_benchmark,
                  'callback': callback,
                  'errback': errback,
                  'save': True}
        Thread(target=callback_wrapper, kwargs=kwargs).start()
