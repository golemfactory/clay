from golem.appconfig import CommonConfig
from golem.core.simpleconfig import SimpleConfig
from golem.testutils import TempDirFixture


class TestSimpleConfig(TempDirFixture):
    def test_config_file(self):
        common_config = CommonConfig(option1="option1", option2=13131, option3="1.13013")
        node_config = CommonConfig(section="Node", noption1="noption1", noption2=24242, noption3="2.24024")
        cfg_file = self.additional_dir_content([1])[0]
        cfg = SimpleConfig(common_config, node_config, cfg_file)
        assert isinstance(cfg, SimpleConfig)
        with open(cfg_file) as f:
            text = f.read()
        assert "option1 = option1" in text
        assert "option2 = 13131" in text
        assert "option3 = 1.13013" in text
        assert "noption1 = noption1" in text
        assert "noption2 = 24242" in text
        assert "noption3 = 2.24024" in text

        common_config = CommonConfig(option1="optionX", option2=23232, option3="2.13013")
        node_config = CommonConfig(section="Node", noption1="noptionY", noption2=14242, noption3="1.24024")
        cfg = SimpleConfig(common_config, node_config, cfg_file)
        with open(cfg_file) as f:
            text = f.read()
        assert "option1 = option1" in text
        assert "option2 = 13131" in text
        assert "option3 = 1.13013" in text
        assert "noption1 = noption1" in text
        assert "noption2 = 24242" in text
        assert "noption3 = 2.24024" in text
        common_config = CommonConfig(option1="optionX", option3="2.13013", option4=4179)
        node_config = CommonConfig(section="Node", noption1="noptionY", noption3="1.24024", noption4="NEWOPTION")
        cfg = SimpleConfig(common_config, node_config, cfg_file)

        with open(cfg_file) as f:
            text = f.read()
        assert "option1 = option1" in text
        assert "option2 = 13131" in text
        assert "option3 = 1.13013" in text
        assert "option4 = 4179" in text
        assert "noption1 = noption1" in text
        assert "noption2 = 24242" in text
        assert "noption3 = 2.24024" in text
        assert "noption4 = NEWOPTION" in text

        cfg = SimpleConfig(common_config, node_config, cfg_file, keep_old=False)

        with open(cfg_file) as f:
            text = f.read()
        assert "option1 = option1" in text
        assert "option2 = 13131" not in text
        assert "option3 = 1.13013" in text
        assert "option4 = 4179" in text
        assert "noption1 = noption1" in text
        assert "noption2 = 24242" not in text
        assert "noption3 = 2.24024" in text
        assert "noption4 = NEWOPTION" in text