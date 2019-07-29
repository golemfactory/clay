from unittest import TestCase
from unittest.mock import MagicMock

from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase as TwistedTestCase

from golem.envs import Environment
from golem.model import Performance
from golem.task.task_api import TaskApiPayloadBuilder
from golem.task.envmanager import EnvironmentManager
from golem.testutils import DatabaseFixture


class EnvManagerBaseTest(TestCase):
    def setUp(self):
        super().setUp()
        self.manager = EnvironmentManager()

    def register_env(self, env_id):
        env = MagicMock(spec=Environment)
        env.metadata().id = env_id
        payload_builder = MagicMock(sepc_set=TaskApiPayloadBuilder)
        self.manager.register_env(env, payload_builder)
        return env, payload_builder


class TestEnvironmentManager(EnvManagerBaseTest):

    def test_register_env(self):
        # Given
        self.assertEqual(self.manager.environments(), [])
        self.assertEqual(self.manager.state(), {})

        # When
        env, _ = self.register_env("env1")

        # Then
        self.assertEqual(self.manager.environments(), [env])
        self.assertEqual(self.manager.state(), {"env1": False})

    def test_re_register_env(self):
        # Given
        env, _ = self.register_env("env1")
        self.manager.set_enabled("env1", True)
        self.assertEqual(self.manager.environments(), [env])
        self.assertTrue(self.manager.enabled("env1"))

        # When
        self.manager.register_env(env, MagicMock(spec=TaskApiPayloadBuilder))

        # Then
        self.assertEqual(self.manager.environments(), [env])
        self.assertTrue(self.manager.enabled("env1"))

    def test_set_enabled(self):
        # Given
        self.register_env("env1")
        self.assertFalse(self.manager.enabled("env1"))

        # When
        self.manager.set_enabled("env1", True)
        # Then / Given
        self.assertTrue(self.manager.enabled("env1"))

        # When
        self.manager.set_enabled("env1", False)
        # Then
        self.assertFalse(self.manager.enabled("env1"))

    def test_set_state(self):
        # Given
        self.register_env("env1")
        self.register_env("env2")
        self.assertFalse(self.manager.enabled("env1"))
        self.assertFalse(self.manager.enabled("env2"))

        # When
        self.manager.set_state({
            "env2": True,
            "bogus_env": True
        })

        # Then
        self.assertFalse(self.manager.enabled("env1"))
        self.assertTrue(self.manager.enabled("env2"))
        self.assertFalse(self.manager.enabled("bogus_env"))

    def test_payload_builder(self):
        _, pb = self.register_env("env1")
        self.assertEqual(pb, self.manager.payload_builder("env1"))


class TestEnvironmentManagerDB(  # pylint: disable=too-many-ancestors
        EnvManagerBaseTest,
        DatabaseFixture,
        TwistedTestCase
):
    @inlineCallbacks
    def test_get_performance_running(self):
        # Given
        env_id = "env1"
        env, _ = self.register_env(env_id)
        self.manager._running_benchmark = True

        # When
        result = yield self.manager.get_performance(env_id)

        # Then
        env.run_benchmark.assert_not_called()
        self.assertIsNone(result)

    @inlineCallbacks
    def test_get_performance_disabled_env(self):
        # Given
        env_id = "env1"
        env, _ = self.register_env(env_id)
        self.manager.set_enabled(env_id, False)

        # When

        with self.assertRaisesRegex(
            Exception,
            'Requested performance for disabled environment'
        ):
            yield self.manager.get_performance(env_id)

        # Then
        env.run_benchmark.assert_not_called()

    @inlineCallbacks
    def test_get_performance_in_db(self):
        # Given
        perf = 300.0
        env_id = "env1"
        env, _ = self.register_env(env_id)
        self.manager.set_enabled(env_id, True)

        Performance.update_or_create(env_id, perf)

        # When
        result = yield self.manager.get_performance(env_id)

        # Then
        env.run_benchmark.assert_not_called()
        self.assertEqual(result, perf)

    @inlineCallbacks
    def test_get_performance_benchmark_error(self):
        # Given
        env_id = "env1"
        env, _ = self.register_env(env_id)
        env.get_benchmark = MagicMock(side_effect=Exception)

        self.manager.set_enabled(env_id, True)

        # When
        yield self.manager.get_performance(env_id)

        # Then
        env.run_benchmark.assert_called_once()
