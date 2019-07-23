from scripts.node_integration_tests import helpers


from ...test_config_base import TestConfigBase


class TestConfig(TestConfigBase):
    def __init__(self):
        super().__init__(task_settings='jpg')

    def update_task_dict(self):
        self.task_package = 'test_task_1'
        super().update_task_dict()
