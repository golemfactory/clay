from ....test_config_base import TestConfigBase


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__()
        self.requestor.concent = 'disabled'
        self.provider.concent = 'disabled'
