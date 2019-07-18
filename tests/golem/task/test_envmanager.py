from unittest import TestCase
from unittest.mock import MagicMock

from golem.envs import Environment
from golem.task.task_api import TaskApiPayloadBuilder
from golem.task.envmanager import EnvironmentManager


class TestEnvironmentManager(TestCase):

    def setUp(self):
        self.manager = EnvironmentManager()

    def register_env(self, env_id):
        env = MagicMock(spec=Environment)
        env.metadata().id = env_id
        payload_builder = MagicMock(sepc_set=TaskApiPayloadBuilder)
        self.manager.register_env(env, payload_builder)
        return env, payload_builder

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
