from os import path

from golem.appconfig import AppConfig, ClientConfigDescriptor
from golem.tools.testdirfixture import TestDirFixture



class TestAppConfig(TestDirFixture):

    def test_load_config(self):
        dir1 = path.join(self.path, "1")
        dir2 = path.join(self.path, "2")
        cfg1 = AppConfig.load_config(dir1, "test.ini")
        with self.assertRaises(RuntimeError):
            AppConfig.load_config(dir1, "test.ini")
        cfg2 = AppConfig.load_config(dir2, "test.ini")

        assert cfg1.config_file == path.join(dir1, "test.ini")
        assert cfg2.config_file == path.join(dir2, "test.ini")

        config_desc = ClientConfigDescriptor()
        config_desc.init_from_app_config(cfg1)
        config_desc.computing_trust = 0.23
        cfg1.change_config(config_desc)

        AppConfig._AppConfig__loaded_configs = set()  # Allow reload.

        cfgC = AppConfig.load_config(dir1, "test.ini")
        assert cfg1.get_node_name() == cfgC.get_node_name()
        config_descC = ClientConfigDescriptor()
        config_descC.init_from_app_config(cfgC)
        assert config_descC.computing_trust == 0.23

        with self.assertRaises(TypeError):
            cfgC.change_config(None)
