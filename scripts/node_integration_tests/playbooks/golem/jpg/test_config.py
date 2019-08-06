from scripts.node_integration_tests import helpers


from ...test_config_base import TestConfigBase


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__(task_settings='jpg')

    def update_task_dict(self):
        self.task_package = 'test_task_1'
        super().update_task_dict()
        self.task_dict['main_scene_file'] = helpers.scene_file_path(
            task_package_name='test_task_1',
            file_path='wlochaty3.blend',
        )
