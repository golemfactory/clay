from unittest import TestCase
from unittest.mock import MagicMock, Mock

from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase as TwistedTestCase

from golem.envs import Environment, EnvMetadata
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
        metadata = EnvMetadata(id=env_id)
        payload_builder = MagicMock(sepc_set=TaskApiPayloadBuilder)
        self.manager.register_env(env, metadata, payload_builder)
        return env, metadata, payload_builder


class TestEnvironmentManager(EnvManagerBaseTest):

    def test_register_env(self):
        # Given
        self.assertEqual(self.manager.environments(), [])
        self.assertEqual(self.manager.state(), {})

        # When
        env, *_ = self.register_env("env1")

        # Then
        self.assertEqual(self.manager.environments(), ["env1"])
        self.assertEqual(self.manager.environment("env1"), env)
        self.assertEqual(self.manager.state(), {"env1": False})

    def test_re_register_env(self):
        # Given
        env, metadata, _ = self.register_env("env1")
        self.manager.set_enabled("env1", True)
        self.assertEqual(self.manager.environments(), ["env1"])
        self.assertTrue(self.manager.enabled("env1"))

        # When
        with self.assertRaises(ValueError):
            self.manager.register_env(
                env,
                metadata,
                MagicMock(spec=TaskApiPayloadBuilder))

        # Then
        self.assertEqual(self.manager.environments(), ["env1"])
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
        *_, pb = self.register_env("env1")
        self.assertEqual(pb, self.manager.payload_builder("env1"))


class TestEnvironmentManagerDB(  # pylint: disable=too-many-ancestors
        EnvManagerBaseTest,
        DatabaseFixture,
        TwistedTestCase
):

    def setUp(self):
        super().setUp()
        self.env_id = "env1"
        self.env, *_ = self.register_env(self.env_id)

    @inlineCallbacks
    def test_get_performance_running(self):
        # Given
        self.manager._running_benchmark = True

        # When
        result = yield self.manager.get_performance(self.env_id)

        # Then
        self.env.run_benchmark.assert_not_called()
        self.assertIsNone(result)

    @inlineCallbacks
    def test_get_performance_disabled_env(self):
        # Given
        self.manager.set_enabled(self.env_id, False)

        # When

        with self.assertRaisesRegex(
            Exception,
            'Requested performance for disabled environment'
        ):
            yield self.manager.get_performance(self.env_id)

        # Then
        self.env.run_benchmark.assert_not_called()

    @inlineCallbacks
    def test_get_performance_in_db(self):
        # Given
        perf = 300.0
        self.manager.set_enabled(self.env_id, True)

        Performance.update_or_create(self.env_id, perf)

        # When
        result = yield self.manager.get_performance(self.env_id)

        # Then
        self.env.run_benchmark.assert_not_called()
        self.assertEqual(result, perf)

    @inlineCallbacks
    def test_get_performance_benchmark_error(self):
        # Given
        error_msg = "Benchmark failed"
        self.env.run_benchmark = Mock(side_effect=Exception(error_msg))

        self.manager.set_enabled(self.env_id, True)

        # When
        result = None
        with self.assertRaisesRegex(Exception, error_msg):
            result = yield self.manager.get_performance(self.env_id)

        # Then
        self.env.run_benchmark.assert_called_once()
        self.assertIsNone(result)

    def test_cached_performance(self):
        self.assertIsNone(self.manager.get_cached_performance(self.env_id))

        perf = 123.4
        Performance.update_or_create(self.env_id, perf)
        self.assertEqual(perf, self.manager.get_cached_performance(self.env_id))
