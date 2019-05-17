from ...test_config_base import TestConfigBase, NodeId


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__()
        self.nodes[NodeId.requestor].script = 'requestor/no_sra'
