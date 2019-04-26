from ..test_config_base import TestConfigBase


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__()
        self.provider.opts = {
            'min_price': 0,
        }
        self.requestor.opts = {
            'max_price': 0,
        }
        self.task_dict['bid'] = 0
