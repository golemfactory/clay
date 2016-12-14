from mock import Mock

from golem.interface.client.tasks import CommandAppLogic
from golem.tools.testdirfixture import TestDirFixture


class TestCommandAppLogic(TestDirFixture):
    def test_renderer_logic(self):
        lgc = CommandAppLogic.instantiate(Mock(), self.path)
        assert lgc.task_types['Blender'] is not None
        assert lgc.task_types['LuxRender'] is not None
