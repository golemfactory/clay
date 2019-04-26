from ...test_config_base import TestConfigBase, make_node_config_from_env


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__()
        provider_config = make_node_config_from_env('PROVIDER', 1)
        provider_config.script = 'provider/no_wtct_after_ttc'
        provider_config_2 = make_node_config_from_env('PROVIDER', 1)
        self.provider = [
            provider_config,
            provider_config_2,
        ]
        self.task_settings = '2_short'
