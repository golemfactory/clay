from golem.appconfig import CommonConfig
from golem.core.simpleconfig import SimpleConfig
from golem.testutils import TempDirFixture


class TestSimpleConfig(TempDirFixture):
    def test_config_file(self):
        common_config = CommonConfig(option1="option1", option2=13131, option3="1.13013")
        node_config = CommonConfig(section="Node", noption1="noption1", noption2=24242, noption3="2.24024")
        cfg_file = self.additional_dir_content([1])[0]
        cfg = SimpleConfig(common_config, node_config, cfg_file)
        self.assertTrue(isinstance(cfg, SimpleConfig))
        with open(cfg_file) as f:
            text = f.read()
        self.assertIn("option1 = option1", text)
        self.assertIn("option2 = 13131", text)
        self.assertIn("option3 = 1.13013", text)
        self.assertIn("noption1 = noption1", text)
        self.assertIn("noption2 = 24242", text)
        self.assertIn("noption3 = 2.24024", text)

        common_config = CommonConfig(option1="optionX", option2=23232, option3="2.13013")
        node_config = CommonConfig(section="Node", noption1="noptionY", noption2=14242, noption3="1.24024")
        SimpleConfig(common_config, node_config, cfg_file)
        with open(cfg_file) as f:
            text = f.read()
        self.assertIn("option1 = option1", text)
        self.assertIn("option2 = 13131", text)
        self.assertIn("option3 = 1.13013", text)
        self.assertIn("noption1 = noption1", text)
        self.assertIn("noption2 = 24242", text)
        self.assertIn("noption3 = 2.24024", text)
        common_config = CommonConfig(option1="optionX", option3="2.13013", option4=4179)
        node_config = CommonConfig(section="Node", noption1="noptionY", noption3="1.24024", noption4="NEWOPTION")
        SimpleConfig(common_config, node_config, cfg_file)

        with open(cfg_file) as f:
            text = f.read()
        self.assertIn("option1 = option1", text)
        self.assertIn("option2 = 13131", text)
        self.assertIn("option3 = 1.13013", text)
        self.assertIn("option4 = 4179", text)
        self.assertIn("noption1 = noption1", text)
        self.assertIn("noption2 = 24242", text)
        self.assertIn("noption3 = 2.24024", text)
        self.assertIn("noption4 = NEWOPTION", text)

        SimpleConfig(common_config, node_config, cfg_file, keep_old=False)

        with open(cfg_file) as f:
            text = f.read()
        self.assertIn("option1 = option1", text)
        self.assertNotIn("option2 = 13131", text)
        self.assertIn("option3 = 1.13013", text)
        self.assertIn("option4 = 4179", text)
        self.assertIn("noption1 = noption1", text)
        self.assertNotIn("noption2 = 24242", text)
        self.assertIn("noption3 = 2.24024", text)
        self.assertIn("noption4 = NEWOPTION", text)

        common_config = CommonConfig(option1="abc", option2=123456, option3="3.1415926")
        SimpleConfig(common_config, node_config, cfg_file, refresh=True, keep_old=False)

        with open(cfg_file) as f:
            text = f.read()
        self.assertIn("option1 = abc", text)
        self.assertIn("option2 = 123456", text)
        self.assertIn("option3 = 3.1415926", text)
        self.assertIn("noption1 = noption1", text)
        self.assertIn("noption3 = 2.24024", text)
        self.assertIn("noption4 = NEWOPTION", text)

    def test_get_config(self):
        common_config = CommonConfig(option1="option1", option2=13131, option3="1.13013")
        node_config = CommonConfig(section="Node", noption1="noption1", noption2=24242, noption3="2.24024")
        cfg_file = self.additional_dir_content([1])[0]
        cfg = SimpleConfig(common_config, node_config, cfg_file)
        common_config2 = cfg.get_common_config()
        node_config2 = cfg.get_node_config()
        self.assertEqual(common_config.option1, common_config2.option1)
        self.assertEqual(common_config.option2, common_config2.option2)
        self.assertEqual(common_config.option3, common_config2.option3)
        self.assertEqual(node_config.section, node_config2.section)
        self.assertEqual(node_config.noption1, node_config2.noption1)
        self.assertEqual(node_config.noption2, node_config2.noption2)
        self.assertEqual(node_config.noption3, node_config2.noption3)

