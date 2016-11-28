from mock import Mock

from golem.tools.testdirfixture import TestDirFixture

from gui.startapp import register_rendering_task_types

from gui.application import GNRGui
from gnr.customizers.renderingnewtaskdialogcustomizer import RenderingNewTaskDialogCustomizer
from gnr.renderingapplicationlogic import RenderingApplicationLogic
from gnr.renderingtaskstate import RenderingTaskDefinition, RendererInfo, RendererDefaults
from gnr.ui.appmainwindow import AppMainWindow


class TestRenderingNewTaskDialogCustomizer(TestDirFixture):
    def setUp(self):
        super(TestRenderingNewTaskDialogCustomizer, self).setUp()
        self.logic = RenderingApplicationLogic()
        self.gnrgui = GNRGui(self.logic, AppMainWindow)

    def tearDown(self):
        self.gnrgui.app.exit(0)
        self.gnrgui.app.deleteLater()
        super(TestRenderingNewTaskDialogCustomizer, self).tearDown()

    def test_customizer(self):
        self.logic.client = Mock()
        self.logic.client.config_desc = Mock()
        self.logic.client.config_desc.max_price = 0
        self.logic.client.get_config.return_value = self.logic.client.config_desc
        self.logic.dir_manager = Mock()
        self.logic.dir_manager.root_path = self.path

        register_rendering_task_types(self.logic)
        customizer = RenderingNewTaskDialogCustomizer(self.gnrgui.main_window, self.logic)
        self.assertIsInstance(customizer, RenderingNewTaskDialogCustomizer)

        definition = RenderingTaskDefinition()
        renderer = RendererInfo("Blender", RendererDefaults(), Mock(), Mock(), Mock(), Mock())
        assert renderer.name == "Blender"
        assert renderer.renderer_options is not None
        definition.renderer = renderer.name
        definition.renderer_options = Mock()
        definition.renderer_options.use_frames = False
        definition.renderer_options.compositing = False
        resources = self.additional_dir_content([3])
        definition.renderer_options.remove_from_resources.return_value = set(resources[0:1])
        definition.renderer_options.add_to_resources.return_value = set(resources[0:1])
        definition.resources = set(resources)
        self.logic.customizer = Mock()
        self.logic.renderers[renderer.name] = renderer
        customizer.load_task_definition(definition)
        assert len(definition.resources) == 3
        customizer.gui.ui.taskNameLineEdit.setText("NEW NAME")
        definition2 = customizer._query_task_definition()
        assert definition2.task_name == "NEW NAME"
