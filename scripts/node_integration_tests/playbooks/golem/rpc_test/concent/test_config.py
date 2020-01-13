from ....test_config_base import CONCENT_STAGING
from ..test_config import TestConfig as RpcTestConfigBase


class TestConfig(RpcTestConfigBase):
    def __init__(self):
        super().__init__()
        for node_config in self.nodes.values():
            node_config.concent = CONCENT_STAGING
