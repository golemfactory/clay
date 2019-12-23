from ..concent_config_base import ConcentTestConfigBase
from ...test_config_base import make_node_config_from_env, NodeId


class TestConfig(ConcentTestConfigBase):
    def __init__(self):
        super().__init__()
        requestor_config = make_node_config_from_env(NodeId.requestor.value, 0)
        requestor_config.script = 'requestor/day_backwards_dont_pay'
        requestor_config_2 = make_node_config_from_env(
            NodeId.requestor.value, 0)
        requestor_config_2.script = 'requestor/dont_pay'
        self.nodes[NodeId.requestor] = [
            requestor_config,
            requestor_config_2,
        ]

        provider_config = make_node_config_from_env(NodeId.provider.value, 1)
        provider_config.script = 'provider/day_backwards'
        provider_config_2 = make_node_config_from_env(NodeId.provider.value, 1)
        self.nodes[NodeId.provider] = [
            provider_config,
            provider_config_2,
        ]
        self.enable_concent()
