import shutil
from copy import copy
import hashlib
import json
import logging
from threading import Thread
from typing import Any, Dict, Union, Optional, TYPE_CHECKING

from golem_task_api import ProviderAppClient

from apps.core.benchmark.benchmarkrunner import BenchmarkRunner
from apps.core.task.coretaskstate import TaskDesc
from golem.core.threads import callback_wrapper
from golem.environments.environment import Environment as DefaultEnvironment

from golem.model import Performance, AppBenchmark
from golem.resource.dirmanager import DirManager
from golem.task import ComputationType
from golem.task.exceptions import ComputationInProgress
from golem.task.task_api import EnvironmentTaskApiService
from golem.task.taskstate import TaskStatus

if TYPE_CHECKING:
    # pylint:disable=unused-import, ungrouped-imports
    from pathlib import Path

    from golem.envs import BenchmarkResult, EnvId
    from golem.task.envmanager import EnvironmentManager


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

        def success_callback(result: 'BenchmarkResult'):
            logger.info('%s benchmark finished. performance=%.2f, cpu_usage=%d',
                        env_id, result.performance, result.cpu_usage)

            Performance.update_or_create(
                env_id=env_id,
                performance=result.performance,
                cpu_usage=result.cpu_usage
            )

            if success:
                success(result.performance)

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
            benchmark=benchmark
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


def hash_prereq_dict(dictionary: Dict[str, Any]) -> str:
    serialized = json.dumps(dictionary, sort_keys=True)
    return hashlib.blake2b(  # pylint: disable=no-member
        serialized.encode('utf-8'),
        digest_size=16
    ).hexdigest()


class AppBenchmarkManager:

    def __init__(
            self,
            env_manager: 'EnvironmentManager',
            root_path: 'Path',
    ) -> None:
        self._env_manager = env_manager
        self._root_path = root_path / 'benchmarks'
        self._computing: Optional[str] = None

    async def get(
            self,
            env_id: 'EnvId',
            env_prereq_dict: Dict[str, Any],
    ) -> AppBenchmark:
        prereq_hash = hash_prereq_dict(env_prereq_dict)

        try:
            return AppBenchmark.get(hash=prereq_hash)
        except AppBenchmark.DoesNotExist:
            pass

        if self._computing:
            raise ComputationInProgress(
                comp_type=ComputationType.BENCHMARK,
                comp_id=self._computing)

        try:
            self._computing = prereq_hash
            score = await self._run_benchmark(env_id, env_prereq_dict)
        finally:
            self._computing = None

        benchmark = AppBenchmark(hash=prereq_hash, score=score)
        benchmark.save()
        return benchmark

    @staticmethod
    def remove_benchmark_scores() -> None:
        AppBenchmark.delete().execute()

    async def _run_benchmark(
            self,
            env_id: 'EnvId',
            env_prereq_dict: Dict[str, Any]
    ) -> float:
        env = self._env_manager.environment(env_id)
        prereq_hash = hash_prereq_dict(env_prereq_dict)

        shared_dir = self._root_path / prereq_hash
        shared_dir.mkdir(parents=True, exist_ok=True)

        task_api_service = EnvironmentTaskApiService(
            env=env,
            payload_builder=self._env_manager.payload_builder(env_id),
            prereq=env.parse_prerequisites(env_prereq_dict),
            shared_dir=shared_dir
        )

        try:
            app_client = await ProviderAppClient.create(task_api_service)
            return await app_client.run_benchmark()
        finally:
            shutil.rmtree(shared_dir)
