from scripts.node_integration_tests import helpers


from ...test_config_base import TestConfigBase


class TestConfig(TestConfigBase):
    def update_task_dict(self):
        super().update_task_dict()
        self.task_dict['main_scene_file'] = helpers.scene_file_path(
            task_package_name='column',
            file_path='the_column.blend',
        )
