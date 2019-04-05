from unittest import TestCase
from unittest.mock import MagicMock

from golem.envs import Environment
from golem.envs.manager import EnvironmentManager


class TestEnvironmentManager(TestCase):

    def setUp(self):
        self.manager = EnvironmentManager()

    @staticmethod
    def new_env(env_id):
        env = MagicMock(spec=Environment)
        env.metadata().id = env_id
        return env

    def test_register_env(self):
        # Given
        self.assertEqual(self.manager.environments(), [])
        self.assertEqual(self.manager.state(), {})

        # When
        env = self.new_env("env1")
        self.manager.register_env(env)

        # Then
        self.assertEqual(self.manager.environments(), [env])
        self.assertEqual(self.manager.state(), {"env1": False})

    def test_re_register_env(self):
        # Given
        env = self.new_env("env1")
        self.manager.register_env(env)
        self.manager.set_enabled("env1", True)
        self.assertEqual(self.manager.environments(), [env])
        self.assertTrue(self.manager.enabled("env1"))

        # When
        self.manager.register_env(env)

        # Then
        self.assertEqual(self.manager.environments(), [env])
        self.assertTrue(self.manager.enabled("env1"))

    def test_set_enabled(self):
        # Given
        env = self.new_env("env1")
        self.manager.register_env(env)
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
        env1 = self.new_env("env1")
        env2 = self.new_env("env2")
        self.manager.register_env(env1)
        self.manager.register_env(env2)
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
        self.assertRaises(KeyError, self.manager.enabled, "bogus_env")
