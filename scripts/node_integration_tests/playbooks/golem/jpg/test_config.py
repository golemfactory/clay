from ...test_config_base import TestConfigBase


class TestConfig(TestConfigBase):
    def update_task_dict(self):
        super().update_task_dict()
        self.task_dict['options']['format'] = 'JPG'
