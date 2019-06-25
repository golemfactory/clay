from aenum import extend_enum
from ...test_config_base import (
    TestConfigBase,
    make_node_config_from_env,
    NodeId
)

import tasks
import pathlib

extend_enum(NodeId, 'provider2', 'provider2')


class TestConfig(TestConfigBase):
    def __init__(self, *, task_settings: str = 'WASM_g_flite') -> None:
        super().__init__(task_settings=task_settings)
        self.task_package = 'test_wasm_task_0'
        self.task_settings = 'WASM_g_flite'
        settings = tasks.get_settings(task_settings)
        cwd = pathlib.Path(__file__).resolve().parent
        settings['options']['input_dir'] = str((cwd / '..' / '..' / '..' /
                                                'tasks' / self.task_package /
                                                'in').resolve())
        settings['options']['output_dir'] = str((cwd / '..' / '..' / '..' /
                                                 'tasks' / self.task_package /
                                                 'out').resolve())
        self.nodes[NodeId.provider2] = make_node_config_from_env(
            NodeId.provider2.value, 2
        )
        self.task_dict = settings
