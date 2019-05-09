from ...test_config_base import (
    TestConfigBase, make_node_config_from_env, NodeId)


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__()
        requestor_config = make_node_config_from_env(
            NodeId.requestor.value.upper(), 0)
        requestor_config_2 = make_node_config_from_env(
            NodeId.requestor.value.upper(), 0)
        requestor_config_2.script = 'requestor/always_accept_provider'
        self.nodes[NodeId.requestor] = [
            requestor_config,
            requestor_config_2,
        ]
