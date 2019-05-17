from ..test_config_base import TestConfigBase


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__()
        for node_config in self.nodes.values():
            node_config.concent = 'disabled'
