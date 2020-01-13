from ...test_config_base import CONCENT_DISABLED
from ...test_config_base import TestConfigBase, NodeId


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__()
        del self.nodes[NodeId.requestor]
        for node_config in self.nodes.values():
            node_config.concent = CONCENT_DISABLED
