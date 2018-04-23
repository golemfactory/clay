import logging
import os
from threading import Thread
from typing import Union

from pydispatch import dispatcher

from apps.core.benchmark.benchmarkrunner import BenchmarkRunner
from apps.core.task.coretaskstate import TaskDesc
import golem
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.threads import callback_wrapper
from golem.environments.environment import Environment as DefaultEnvironment
from golem.model import Performance
from golem.resource.dirmanager import DirManager
from golem.task.taskbase import Task
from golem.task.taskstate import TaskStatus

logger = logging.getLogger(__name__)


class BenchmarkManager(object):
    def __init__(self, config_desc: ClientConfigDescriptor, task_server,
                 root_path, benchmarks=None) -> None:
        self.config_desc = config_desc
        self.benchmarks = benchmarks
        self.task_server = task_server
        self.dir_manager = DirManager(root_path)
        if not self.benchmarks_needed():
            current_results = self._get_current_results()
            self._publish_results(current_results)

    @staticmethod
    def _get_current_results():
        query = Performance.select().where(
            Performance.golem_version == golem.__version__)
        return {perf.environment_id: perf.value for perf in query}

    @staticmethod
    def _publish_results(results):
        if results:
            dispatcher.send(
                signal='golem.benchmarks',
                event='benchmarks_results_published',
                results=results
            )

    def _get_all_benchmark_ids(self):
        benchmark_ids = {DefaultEnvironment.get_id()}
        if self.benchmarks:
            benchmark_ids.update(self.benchmarks.keys())
        return benchmark_ids

    def benchmarks_needed(self):
        query = Performance.select(Performance.environment_id).where(
            Performance.golem_version == golem.__version__)
        data = set(benchmark.environment_id for benchmark in query)
        all_benchmark_ids = self._get_all_benchmark_ids()
        return not all_benchmark_ids.issubset(data)

    def run_default_benchmark(self, callback, errback=None):

        def wrapped_errback(err):
            logger.error('Running default benchmark failed: %s', str(err))
            if errback is not None:
                errback(err)

        kwargs = {
            'func': DefaultEnvironment.run_default_benchmark,
            'callback': callback,
            'errback': wrapped_errback,
            'num_cores': self.config_desc.num_cores,
            'save': True
        }
        Thread(target=callback_wrapper, kwargs=kwargs).start()

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
        all_benchmark_ids = self._get_all_benchmark_ids()
        self.run_benchmarks(all_benchmark_ids, success, error)

    def run_benchmarks(self, benchmark_ids, success=None, error=None):
        benchmark_ids_iter = iter(benchmark_ids)
        results = {}
        env_id = None

        # Next benchmark is run only if the previous one completed successfully
        def _run(performance_value):
            nonlocal env_id
            if env_id is not None:
                results[env_id] = performance_value
            env_id = next(benchmark_ids_iter, None)
            if env_id is None:
                self._publish_results(results)
                if success:
                    success(results)
            else:
                self.run_benchmark_for_env_id(env_id, _run, error)

        _run(None)

    @staticmethod
    def _validate_task_state(task_state):
        td = task_state.definition
        if not os.path.exists(td.main_program_file):
            logger.error("Main program file does not exist: {}".format(
                td.main_program_file))
            return False
        return True

    def run_benchmark_for_env_id(self, env_id, callback, errback):
        if env_id != DefaultEnvironment.get_id():
            benchmark_data = self.benchmarks.get(env_id)
            if benchmark_data:
                self.run_benchmark(benchmark_data[0], benchmark_data[1],
                                   env_id, callback, errback)
            else:
                raise Exception("Unknown environment: {}".format(env_id))
        else:
            self.run_default_benchmark(callback, errback)
