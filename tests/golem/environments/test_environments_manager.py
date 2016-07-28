import unittest

from golem.environments.environmentsmanager import EnvironmentsManager
from golem.environments.environment import Environment

import logging

logger = logging.getLogger(__name__)

class TestEnvironmentsManager(unittest.TestCase):
    def test_get_environment_by_id(self):
        em = EnvironmentsManager()
        env1 = Environment()
        env2 = Environment()
        env3 = Environment()
        env1.get_id = lambda : "Env1"
        env2.get_id = lambda : "Env2"
        env3.get_id = lambda : "Env3"
        em.add_environment(env1)
        em.add_environment(env2)
        em.add_environment(env3)
        self.assertTrue(env1 == em.get_environment_by_id("Env1"))
        self.assertTrue(env2 == em.get_environment_by_id("Env2"))
        self.assertTrue(env3 == em.get_environment_by_id("Env3"))
        