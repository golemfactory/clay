from mock import Mock

from golem.tools.testdirfixture import TestDirFixture

from gnr.application import GNRGui
from gnr.customizers.renderingnewtaskdialogcustomizer import RenderingNewTaskDialogCustomizer
from gnr.gnrstartapp import register_rendering_task_types
from gnr.renderingapplicationlogic import RenderingApplicationLogic
from gnr.renderingtaskstate import RenderingTaskDefinition, RendererInfo, RendererDefaults
from gnr.ui.appmainwindow import AppMainWindow


class TestRenderingNewTaskDialogCustomizer(TestDirFixture):
    def setUp(self):
        super(TestRenderingNewTaskDialogCustomizer, self).setUp()
        self.gnrgui = GNRGui(Mock(), AppMainWindow)

    def tearDown(self):
        super(TestRenderingNewTaskDialogCustomizer, self).tearDown()
        self.gnrgui.app.exit(0)
        self.gnrgui.app.deleteLater()

    def test_customizer(self):
        logic = RenderingApplicationLogic()
        logic.client = Mock()
        register_rendering_task_types(logic)
        customizer = RenderingNewTaskDialogCustomizer(self.gnrgui.main_window, logic)
        self.assertIsInstance(customizer, RenderingNewTaskDialogCustomizer)

        definition = RenderingTaskDefinition()
        renderer = RendererInfo("Blender", RendererDefaults(), Mock(), Mock(), Mock(), Mock())
        assert renderer.name == "Blender"
        assert renderer.renderer_options is not None
        definition.renderer = renderer.name
        definition.renderer_options = Mock()
        definition.renderer_options.use_frames = False
        resources = self.additional_dir_content([3])
        definition.renderer_options.remove_from_resources.return_value = set(resources[0:1])
        definition.resources = set(resources)
        logic.customizer = Mock()
        logic.renderers[renderer.name] = renderer
        customizer.load_task_definition(definition)
        assert len(definition.resources) == 3


