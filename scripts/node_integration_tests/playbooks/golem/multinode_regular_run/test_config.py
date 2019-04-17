from aenum import extend_enum
from ...test_config_base import TestConfigBase, NodeId, \
    make_node_config_from_env


extend_enum(NodeId, 'provider2', 'provider2')


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__()
        self.nodes[NodeId.provider2] = make_node_config_from_env(
            NodeId.provider2.value.upper(), 2)
        self.task_dict['subtasks_count'] = 2
