import asyncio
import unittest
from pathlib import Path

from golem_task_api import (
    ProviderAppClient,
    TaskApiService,
    RequestorAppClient
)
from golem_task_api.structs import Subtask
from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase as TwistedTestCase

from golem.core.common import install_reactor
from golem.core.deferred import deferred_from_future
from golem.task.task_api import EnvironmentTaskApiService
from golem.tools.testwithreactor import uninstall_reactor
from tests.golem.envs.localhost import (
    LocalhostEnvironment,
    LocalhostConfig,
    LocalhostPrerequisites,
    LocalhostPayloadBuilder
)


class TestLocalhostEnv(TwistedTestCase):

    @classmethod
    def setUpClass(cls):
        try:
            uninstall_reactor()  # Because other tests don't clean up
        except AttributeError:
            pass
        install_reactor()

    @classmethod
    def tearDownClass(cls):
        uninstall_reactor()

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

    @unittest.skip('LocalhostRuntime.stop is not working properly')  # FIXME
    @inlineCallbacks
    def test_compute_interrupted(self):

        async def compute(_, __):
            await asyncio.sleep(10)
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
        with self.assertRaises(OSError):
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
    def test_subtasks(self):
        subtask = Subtask(
            subtask_id='test_subtask',
            params={'param': 'value'},
            resources=['test_resource']
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

        subtask_future = asyncio.ensure_future(client.next_subtask('whatever'))
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
                return True, None
            elif subtask_id == bad_subtask_id:
                return False, 'test_error'

        prereq = LocalhostPrerequisites(verify=verify)
        service = self._get_service(prereq)
        client_future = asyncio.ensure_future(
            RequestorAppClient.create(service))
        client = yield deferred_from_future(client_future)

        good_verify_future = asyncio.ensure_future(
            client.verify('test_task', good_subtask_id))
        good_verify_result = yield deferred_from_future(good_verify_future)
        self.assertTrue(good_verify_result)

        bad_verify_future = asyncio.ensure_future(
            client.verify('test_task', bad_subtask_id))
        bad_verify_result = yield deferred_from_future(bad_verify_future)
        self.assertFalse(bad_verify_result)

        shutdown_future = asyncio.ensure_future(client.shutdown())
        yield deferred_from_future(shutdown_future)
