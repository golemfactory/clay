from golem.appconfig import CommonConfig
from golem.core.simpleconfig import SimpleConfig
from golem.testutils import TempDirFixture


class TestSimpleConfig(TempDirFixture):
    def test_config_file(self):
        node_config = CommonConfig(section="Node", noption1="noption1", noption2=24242, noption3="2.24024")
        cfg_file = self.additional_dir_content([1])[0]
        cfg = SimpleConfig(node_config, cfg_file)
        self.assertTrue(isinstance(cfg, SimpleConfig))
        with open(cfg_file) as f:
            text = f.read()
        self.assertIn("noption1 = noption1", text)
        self.assertIn("noption2 = 24242", text)
        self.assertIn("noption3 = 2.24024", text)

        node_config = CommonConfig(section="Node", noption1="noptionY", noption2=14242, noption3="1.24024")
        SimpleConfig(node_config, cfg_file)
        with open(cfg_file) as f:
            text = f.read()
        self.assertIn("noption1 = noption1", text)
        self.assertIn("noption2 = 24242", text)
        self.assertIn("noption3 = 2.24024", text)
        node_config = CommonConfig(section="Node", noption1="noptionY", noption3="1.24024", noption4="NEWOPTION")
        SimpleConfig(node_config, cfg_file)

        with open(cfg_file) as f:
            text = f.read()
        self.assertIn("noption1 = noption1", text)
        self.assertIn("noption2 = 24242", text)
        self.assertIn("noption3 = 2.24024", text)
        self.assertIn("noption4 = NEWOPTION", text)

        SimpleConfig(node_config, cfg_file, keep_old=False)

        with open(cfg_file) as f:
            text = f.read()
        self.assertIn("noption1 = noption1", text)
        self.assertNotIn("noption2 = 24242", text)
        self.assertIn("noption3 = 2.24024", text)
        self.assertIn("noption4 = NEWOPTION", text)

        SimpleConfig(node_config, cfg_file, refresh=True, keep_old=False)

        with open(cfg_file) as f:
            text = f.read()
        self.assertIn("noption1 = noption1", text)
        self.assertIn("noption3 = 2.24024", text)
        self.assertIn("noption4 = NEWOPTION", text)

    def test_get_config(self):
        node_config = CommonConfig(section="Node", noption1="noption1", noption2=24242, noption3="2.24024")
        cfg_file = self.additional_dir_content([1])[0]
        cfg = SimpleConfig(node_config, cfg_file)
        node_config2 = cfg.get_node_config()
        self.assertEqual(node_config.section, node_config2.section)
        self.assertEqual(node_config.noption1, node_config2.noption1)
        self.assertEqual(node_config.noption2, node_config2.noption2)
        self.assertEqual(node_config.noption3, node_config2.noption3)

