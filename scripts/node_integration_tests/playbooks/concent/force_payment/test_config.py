from ...test_config_base import TestConfigBase, make_node_config_from_env


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__()
        requestor_config = make_node_config_from_env('REQUESTOR', 0)
        requestor_config.script = 'requestor/day_backwards_dont_pay'
        requestor_config_2 = make_node_config_from_env('REQUESTOR', 0)
        requestor_config_2.script = 'requestor/dont_pay'
        self.requestor = [
            requestor_config,
            requestor_config_2,
        ]

        provider_config = make_node_config_from_env('PROVIDER', 1)
        provider_config.script = 'provider/day_backwards'
        provider_config_2 = make_node_config_from_env('PROVIDER', 1)
        self.provider = [
            provider_config,
            provider_config_2,
        ]
