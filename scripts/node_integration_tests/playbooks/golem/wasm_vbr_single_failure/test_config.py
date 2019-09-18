from aenum import extend_enum
from ...test_config_base import (
    TestConfigBase,
    make_node_config_from_env,
    NodeId
)

from pathlib import Path
from scripts.node_integration_tests import helpers

extend_enum(NodeId, 'provider2', 'provider2')
extend_enum(NodeId, 'provider3', 'provider3')

THIS_DIR: Path = Path(__file__).resolve().parent


class TestConfig(TestConfigBase):
    def __init__(self, *, task_settings: str = 'WASM_g_flite') -> None:
        super().__init__(task_settings=task_settings)
        self.task_package = 'test_wasm_task_0'
        self.update_task_dict()
        self.nodes[NodeId.provider2] = make_node_config_from_env(
            NodeId.provider2.value, 2
        )
        # Whatever, we simply want to change `wav.in`.
        self.nodes[NodeId.provider2].opts = {
            'overwrite_results': str(THIS_DIR.parent / "fake_result.png"),
        }

        self.nodes[NodeId.provider3] = make_node_config_from_env(
            NodeId.provider3.value, 3
        )

    def update_task_dict(self):
        self.task_dict = helpers.construct_test_task(
            task_package_name=self.task_package,
            task_settings=self.task_settings,
        )
        cwd = Path(__file__).resolve().parent
        self.task_dict['options']['input_dir'] =\
            str((cwd / '..' / '..' / '..' / 'tasks' / self.task_package /
                'in').resolve())
        self.task_dict['options']['output_dir'] =\
            str((cwd / '..' / '..' / '..' / 'tasks' / self.task_package /
                'out').resolve())
