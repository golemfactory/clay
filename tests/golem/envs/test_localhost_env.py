import asyncio
from pathlib import Path

from golem_task_api import (
    ProviderAppClient,
    TaskApiService,
    RequestorAppClient
)
from golem_task_api.enums import VerifyResult
from golem_task_api.structs import Subtask, Task, Infrastructure
from grpclib.exceptions import StreamTerminatedError
from twisted.internet.defer import inlineCallbacks

from golem.core.deferred import deferred_from_future
from golem.task.task_api import EnvironmentTaskApiService
from tests.golem.envs.localhost import (
    LocalhostEnvironment,
    LocalhostConfig,
    LocalhostPrerequisites,
    LocalhostPayloadBuilder
)
from tests.utils.asyncio import TwistedAsyncioTestCase


class TestLocalhostEnv(TwistedAsyncioTestCase):

    @staticmethod
    def _get_service(prereq: LocalhostPrerequisites) -> TaskApiService:
        env = LocalhostEnvironment(LocalhostConfig())
        return EnvironmentTaskApiService(
            env=env,
            payload_builder=LocalhostPayloadBuilder,
            prereq=prereq,
            shared_dir=Path('whatever')
        )

    @inlineCallbacks
    def test_compute_ok(self):
        subtask_id = 'test_subtask'
        subtask_params = {'param': 'value'}
        result_path = 'test_result'

        async def compute(given_id, given_params):
            assert given_id == subtask_id
            assert given_params == subtask_params
            return result_path

        prereq = LocalhostPrerequisites(compute=compute)
        service = self._get_service(prereq)
        client_future = asyncio.ensure_future(ProviderAppClient.create(service))
        client = yield deferred_from_future(client_future)
        compute_future = asyncio.ensure_future(client.compute(
            task_id='test_task',
            subtask_id=subtask_id,
            subtask_params=subtask_params
        ))
        result = yield deferred_from_future(compute_future)
        self.assertEqual(result, Path(result_path))

    @inlineCallbacks
    def test_compute_interrupted(self):

        async def compute(_, __):
            await asyncio.sleep(20)
            return ''

        prereq = LocalhostPrerequisites(compute=compute)
        service = self._get_service(prereq)
        client_future = asyncio.ensure_future(ProviderAppClient.create(service))
        client = yield deferred_from_future(client_future)
        compute_future = asyncio.ensure_future(client.compute(
            task_id='test_task',
            subtask_id='test_subtask',
            subtask_params={'param': 'value'}
        ))
        yield service._runtime.stop()  # pylint: disable=protected-access
        with self.assertRaises((OSError, StreamTerminatedError)):
            yield deferred_from_future(compute_future)

    @inlineCallbacks
    def test_benchmark(self):
        benchmark_result = 21.37

        async def run_benchmark():
            return benchmark_result

        prereq = LocalhostPrerequisites(run_benchmark=run_benchmark)
        service = self._get_service(prereq)
        client_future = asyncio.ensure_future(ProviderAppClient.create(service))
        client = yield deferred_from_future(client_future)
        benchmark_future = asyncio.ensure_future(client.run_benchmark())
        result = yield deferred_from_future(benchmark_future)
        self.assertAlmostEqual(result, benchmark_result, places=5)

    @inlineCallbacks
    def test_create_task(self):
        task = Task(
            env_id='test_env',
            prerequisites={'key': 'value'},
            inf_requirements=Infrastructure(min_memory_mib=2000.),
        )

        async def create_task():
            return task

        prereq = LocalhostPrerequisites(create_task=create_task)
        service = self._get_service(prereq)
        client = yield deferred_from_future(RequestorAppClient.create(service))
        result = yield deferred_from_future(client.create_task(
            task_id='whatever',
            max_subtasks_count=0,
            task_params={},
        ))
        self.assertEqual(result, task)
        yield deferred_from_future(client.shutdown())

    @inlineCallbacks
    def test_subtasks(self):
        subtask = Subtask(
            params={'param': 'value'},
            resources=['test_resource'],
        )
        subtasks = [subtask]

        async def next_subtask():
            return subtasks.pop(0)

        async def has_pending_subtasks():
            return bool(subtasks)

        prereq = LocalhostPrerequisites(
            next_subtask=next_subtask,
            has_pending_subtasks=has_pending_subtasks
        )
        service = self._get_service(prereq)
        client_future = asyncio.ensure_future(
            RequestorAppClient.create(service))
        client = yield deferred_from_future(client_future)

        pending_subtasks_future = asyncio.ensure_future(
            client.has_pending_subtasks('whatever')
        )
        pending_subtasks = yield deferred_from_future(pending_subtasks_future)
        self.assertTrue(pending_subtasks)

        subtask_future = asyncio.ensure_future(client.next_subtask(
            'whatever', 'whatever', 'whatever'))
        result = yield deferred_from_future(subtask_future)
        self.assertEqual(result, subtask)

        pending_subtasks_future = asyncio.ensure_future(
            client.has_pending_subtasks('whatever')
        )
        pending_subtasks = yield deferred_from_future(pending_subtasks_future)
        self.assertFalse(pending_subtasks)

        shutdown_future = asyncio.ensure_future(client.shutdown())
        yield deferred_from_future(shutdown_future)

    @inlineCallbacks
    def test_verify(self):
        good_subtask_id = 'good_subtask'
        bad_subtask_id = 'bad_subtask'

        async def verify(subtask_id):
            if subtask_id == good_subtask_id:
                return VerifyResult.SUCCESS, None
            elif subtask_id == bad_subtask_id:
                return VerifyResult.FAILURE, 'error'

        prereq = LocalhostPrerequisites(verify=verify)
        service = self._get_service(prereq)
        client = yield deferred_from_future(RequestorAppClient.create(service))

        good_verify_result = yield deferred_from_future(
            client.verify('test_task', good_subtask_id))
        self.assertEqual(good_verify_result, (VerifyResult.SUCCESS, ''))

        bad_verify_result = yield deferred_from_future(
            client.verify('test_task', bad_subtask_id))
        self.assertEqual(bad_verify_result, (VerifyResult.FAILURE, 'error'))

        yield deferred_from_future(client.shutdown())
