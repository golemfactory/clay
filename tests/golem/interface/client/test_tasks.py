from mock import Mock

from golem.interface.client.tasks import RendererLogic
from golem.tools.testdirfixture import TestDirFixture


class TestRendererLogic(TestDirFixture):
    def test_renderer_logic(self):
        rl = RendererLogic.instantiate(Mock(), self.path)
        assert rl.task_types['Blender'] is not None
        assert rl.task_types['LuxRender'] is not None