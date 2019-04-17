from ..no_concent.test_config import TestConfig as TestConfigBase


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__()
        self.requestor.mainnet = True
        self.provider.mainnet = True
