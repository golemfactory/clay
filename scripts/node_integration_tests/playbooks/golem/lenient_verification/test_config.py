from aenum import extend_enum
from pathlib import Path

from ...test_config_base import TestConfigBase, NodeId, \
    make_node_config_from_env


extend_enum(NodeId, 'provider2', 'provider2')

THIS_DIR: Path = Path(__file__).resolve().parent


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__()
        self.nodes[NodeId.provider].opts = {
            'overwrite_results': str(THIS_DIR.parent / "fake_result.png"),
        }
        self.nodes[NodeId.provider2] = make_node_config_from_env(
            NodeId.provider2.value, 2)
        self.task_dict['x-run-verification'] = 'lenient'
