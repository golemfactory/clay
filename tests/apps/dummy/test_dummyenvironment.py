import unittest
from os import path

from apps.dummy.dummyenvironment import DummyTaskEnvironment
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.tools.ci import ci_skip


@ci_skip
class TestDummyEnvironment(unittest.TestCase):
    def test_dummy(self):
        env = DummyTaskEnvironment()
        self.assertIsInstance(env, DummyTaskEnvironment)

    def test_get_performance(self):
        env = DummyTaskEnvironment()
        perf = 1234.5
        cfg_desc = ClientConfigDescriptor()
        cfg_desc.estimated_dummy_performance = perf
        result = env.get_performance(cfg_desc)
        self.assertTrue(result == perf)

    def test_main_program_file(self):
        assert path.isfile(DummyTaskEnvironment().main_program_file)
