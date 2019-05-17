from ..test_config_base import TestConfigBase, NodeId


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__()
        self.nodes[NodeId.provider].opts = {
            'min_price': 0,
        }
        self.nodes[NodeId.requestor].opts = {
            'max_price': 0,
        }
        self.task_dict['bid'] = 0
