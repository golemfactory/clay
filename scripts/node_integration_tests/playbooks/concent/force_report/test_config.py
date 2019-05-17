from ...test_config_base import TestConfigBase, NodeId


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__()
        self.nodes[NodeId.requestor].script = 'requestor/no_ack_rct'
        self.nodes[NodeId.provider].script = 'provider/impatient_frct'
