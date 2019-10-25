from ...test_config_base import TestConfigBase, CONCENT_STAGING


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__()
        for node_config in self.nodes.values():
            node_config.concent = CONCENT_STAGING
