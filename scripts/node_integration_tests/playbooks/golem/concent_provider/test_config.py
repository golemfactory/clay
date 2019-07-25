from ...test_config_base import (
    TestConfigBase, NodeId, CONCENT_STAGING, CONCENT_DISABLED
)


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__(task_settings='2_short')
        self.nodes[NodeId.provider].concent = CONCENT_STAGING
        self.nodes[NodeId.requestor].concent = CONCENT_DISABLED
