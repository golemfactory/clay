from ...test_config_base import (
    TestConfigBase, make_node_config_from_env, NodeId)


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__()
        provider_config = make_node_config_from_env(NodeId.provider.value, 0)
        provider_config.script = 'provider/cannot_compute'
        provider_config_2 = make_node_config_from_env(NodeId.provider.value, 0)

        requestor_config = make_node_config_from_env(NodeId.requestor.value, 1)
        requestor_config_2 = make_node_config_from_env(
            NodeId.requestor.value, 1)
        requestor_config_2.script = 'requestor/always_accept_provider'

        self.nodes[NodeId.requestor] = [
            requestor_config,
            requestor_config_2,
        ]

        self.nodes[NodeId.provider] = [
            provider_config,
            provider_config_2
        ]
