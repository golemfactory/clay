from ...test_config_base import NodeId

from ..task_api.test_config import TestConfig as TestConfigBase


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__()
        self.nodes[NodeId.provider].script = 'provider/configure_or_die'
