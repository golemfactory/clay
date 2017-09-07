import unittest
from os import path

from apps.mlpoc.mlpocenvironment import MLPOCSpearmintEnvironment, MLPOCTorchEnvironment
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.tools.ci import ci_skip


@ci_skip
class TestMLPOCTorchEnvironment(unittest.TestCase):
    def test_dummy(self):
        env = MLPOCTorchEnvironment()
        self.assertIsInstance(env, MLPOCTorchEnvironment)

    def test_get_performance(self):
        env = MLPOCTorchEnvironment()
        perf = 1234.5
        cfg_desc = ClientConfigDescriptor()
        cfg_desc.estimated_dummytask_performance = perf
        result = env.get_performance(cfg_desc)
        self.assertTrue(result == perf)

    def test_main_program_file(self):
        assert path.isfile(MLPOCTorchEnvironment().main_program_file)


@ci_skip
class TestMLPOCSpearmintEnvironment(unittest.TestCase):
    def test_dummy(self):
        env = MLPOCSpearmintEnvironment()
        self.assertIsInstance(env, MLPOCSpearmintEnvironment)

    def test_get_performance(self):
        env = MLPOCSpearmintEnvironment()
        perf = 1234.5
        cfg_desc = ClientConfigDescriptor()
        cfg_desc.estimated_dummytask_performance = perf
        result = env.get_performance(cfg_desc)
        self.assertTrue(result == perf)

    def test_main_program_file(self):
        assert path.isfile(MLPOCSpearmintEnvironment().main_program_file)
