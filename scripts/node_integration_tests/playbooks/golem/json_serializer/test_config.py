from ...test_config_base import TestConfigBase, NodeId


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__()
        self.nodes[NodeId.requestor].script = 'json_serializer'
        # if you remove crossbar-serializer flag below, test should fail with
        # "WAMP message serialization error: huge unsigned int".
        for node_config in self.nodes.values():
            node_config.additional_args = {
                '--crossbar-serializer': 'json',
            }
