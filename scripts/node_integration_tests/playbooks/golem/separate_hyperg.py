from ..test_config_base import TestConfigBase, NodeId


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__()
        self.nodes[NodeId.provider].hyperdrive_port = 3283
        self.nodes[NodeId.provider].hyperdrive_rpc_port = 3293
