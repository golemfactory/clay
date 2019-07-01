from ..test_config_base import TestConfigBase


class ConcentTestConfigBase(TestConfigBase):
    def __init__(self):
        super().__init__()
        for node_config in self.nodes.values():
            node_config.concent = 'staging'
