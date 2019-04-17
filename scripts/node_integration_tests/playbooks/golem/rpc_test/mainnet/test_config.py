from ..no_concent.test_config import TestConfig as TestConfigBase


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__()
        for node_config in self.nodes.values():
            node_config.mainnet = True
