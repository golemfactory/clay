from aenum import extend_enum
from ...test_config_base import (
    TestConfigBase,
    make_node_config_from_env,
    NodeId
)

import tasks
import pathlib
from scripts.node_integration_tests import helpers

extend_enum(NodeId, 'provider2', 'provider2')


class TestConfig(TestConfigBase):
    def __init__(self, *, task_settings: str = 'WASM_g_flite') -> None:
        super().__init__(task_settings=task_settings)
        self.task_package = 'test_wasm_task_0'
        self.update_task_dict()
        self.nodes[NodeId.provider2] = make_node_config_from_env(
            NodeId.provider2.value, 2
        )

    def update_task_dict(self):
        self.task_dict = helpers.construct_test_task(
            task_package_name=self.task_package,
            task_settings=self.task_settings,
        )
        cwd = pathlib.Path(__file__).resolve().parent
        self.task_dict['options']['input_dir'] = str((cwd / '..' / '..' / '..' /
                                                       'tasks' / self.task_package /
                                                       'in').resolve())
        self.task_dict['options']['output_dir'] = str((cwd / '..' / '..' / '..' /
                                                       'tasks' / self.task_package /
                                                       'out').resolve())
