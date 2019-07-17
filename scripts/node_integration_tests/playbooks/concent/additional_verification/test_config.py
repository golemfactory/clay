from ..concent_config_base import ConcentTestConfigBase
from ...test_config_base import NodeId


class TestConfig(ConcentTestConfigBase):
    def __init__(self):
        super().__init__()
        self.nodes[NodeId.requestor].script = 'requestor/reject_results'
