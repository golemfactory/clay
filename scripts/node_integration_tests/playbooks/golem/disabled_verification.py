from pathlib import Path

from ..test_config_base import TestConfigBase, NodeId


THIS_DIR: Path = Path(__file__).resolve().parent


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__()
        self.nodes[NodeId.provider].opts = {
            'overwrite_results': str(THIS_DIR / "fake_result.png"),
        }
        self.task_dict['x-run-verification'] = 'disabled'
