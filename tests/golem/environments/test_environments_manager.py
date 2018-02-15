import logging
import unittest

from golem.environments.environmentsmanager import EnvironmentsManager
from tests.golem.environments.test_environment_class import DummyTestEnvironment

logger = logging.getLogger(__name__)


class TestEnvironmentsManager(unittest.TestCase):
    def setUp(self):
        self.em = EnvironmentsManager()
        self.env1 = DummyTestEnvironment()
        self.env2 = DummyTestEnvironment()
        self.env3 = DummyTestEnvironment()
        self.env1.get_id = lambda: "Env1"
        self.env2.get_id = lambda: "Env2"
        self.env3.get_id = lambda: "Env3"
        self.em.add_environment("type1", self.env1)
        self.em.add_environment("type2", self.env2)
        self.em.add_environment("type3", self.env3)

    def test_get_environment_by_id(self):
        self.assertEqual(self.env1, self.em.get_environment_by_id("Env1"))
        self.assertEqual(self.env2, self.em.get_environment_by_id("Env2"))
        self.assertEqual(self.env3, self.em.get_environment_by_id("Env3"))

    def test_get_environment_by_task_type(self):
        self.assertEqual(self.env1,
                         self.em.get_environment_by_task_type("type1"))
        self.assertEqual(self.env2,
                         self.em.get_environment_by_task_type("type2"))
        self.assertEqual(self.env3,
                         self.em.get_environment_by_task_type("type3"))
