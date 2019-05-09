from ...test_config_base import (
    TestConfigBase, make_node_config_from_env, NodeId)


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__(task_settings='2_short')
        provider_config = make_node_config_from_env(
            NodeId.provider.value.upper(), 1)
        provider_config.script = 'provider/no_wtct_after_ttc'
        provider_config_2 = make_node_config_from_env(
            NodeId.provider.value.upper(), 1)
        self.nodes[NodeId.provider] = [
            provider_config,
            provider_config_2,
        ]
