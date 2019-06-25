from aenum import extend_enum
from ...test_config_base import (
    TestConfigBase,
    make_node_config_from_env,
    NodeId
)

import tasks
from pathlib import Path

extend_enum(NodeId, 'provider2', 'provider2')
extend_enum(NodeId, 'provider3', 'provider3')
extend_enum(NodeId, 'provider4', 'provider4')

THIS_DIR: Path = Path(__file__).resolve().parent


class TestConfig(TestConfigBase):
    def __init__(self, *, task_settings: str = 'WASM_g_flite') -> None:
        super().__init__(task_settings=task_settings)
        self.task_package = 'test_wasm_task_0'
        self.task_settings = 'WASM_g_flite'
        settings = tasks.get_settings(task_settings)
        cwd = Path(__file__).resolve().parent
        settings['options']['input_dir'] = str((cwd / '..' / '..' / '..' /
                                                'tasks' / self.task_package /
                                                'in').resolve())
        settings['options']['output_dir'] = str((cwd / '..' / '..' / '..' /
                                                 'tasks' / self.task_package /
                                                 'out').resolve())

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
        self.nodes[NodeId.provider4] = make_node_config_from_env(
            NodeId.provider4.value, 4
        )

        self.task_dict = settings
