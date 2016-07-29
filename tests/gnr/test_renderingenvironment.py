import logging
import unittest

from gnr.renderingenvironment import BlenderEnvironment, LuxRenderEnvironment
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import config_logging


class BlenderEnvTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        config_logging()

    @classmethod
    def tearDownClass(cls):
        logging.shutdown()

    def test_blender(self):
        env = BlenderEnvironment()
        assert bool(env.supported()) == bool(env.check_software())
        
    def test_get_performance(self):
        env = BlenderEnvironment()
        perf = 2345.2
        cfg_desc = ClientConfigDescriptor()
        cfg_desc.estimated_blender_performance = perf
        result = env.get_performance(cfg_desc)
        self.assertTrue(result == perf)
        

class TestLuxRenderEnvironment(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        config_logging()

    @classmethod
    def tearDownClass(cls):
        logging.shutdown()

    def test_lux(self):
        env = LuxRenderEnvironment()
        self.assertIsInstance(env, LuxRenderEnvironment)

    def test_get_performance(self):
        env = LuxRenderEnvironment()
        perf = 1234.5
        cfg_desc = ClientConfigDescriptor()
        cfg_desc.estimated_lux_performance = perf
        result = env.get_performance(cfg_desc)
        self.assertTrue(result == perf)
