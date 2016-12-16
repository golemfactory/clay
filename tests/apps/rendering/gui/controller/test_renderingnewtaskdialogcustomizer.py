from mock import Mock, patch

from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture

from apps.core.task.gnrtaskstate import GNROptions
from apps.rendering.gui.controller.renderingnewtaskdialogcustomizer import RenderingNewTaskDialogCustomizer, logger
from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition, RendererInfo, RendererDefaults

from gui.application import GNRGui
from gui.applicationlogic import GNRApplicationLogic
from gui.startapp import register_rendering_task_types
from gui.view.appmainwindow import AppMainWindow


class TestRenderingNewTaskDialogCustomizer(TestDirFixture, LogTestCase):
    def setUp(self):
        super(TestRenderingNewTaskDialogCustomizer, self).setUp()
        self.logic = GNRApplicationLogic()
        self.gnrgui = GNRGui(self.logic, AppMainWindow)

    def tearDown(self):
        self.gnrgui.app.exit(0)
        self.gnrgui.app.deleteLater()
        super(TestRenderingNewTaskDialogCustomizer, self).tearDown()

    @patch('apps.rendering.gui.controller.renderingnewtaskdialogcustomizer.QFileDialog')
    def test_customizer(self, file_dialog_mock):
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
        assert renderer.options is not None
        definition.task_type = renderer.name
        definition.options = Mock()
        definition.options.use_frames = False
        definition.options.compositing = False
        resources = self.additional_dir_content([3])
        definition.options.remove_from_resources.return_value = set(resources[0:1])
        definition.options.add_to_resources.return_value = set(resources[0:1])
        definition.resources = set(resources)
        self.logic.customizer = Mock()
        self.logic.task_types[renderer.name] = renderer
        customizer.load_task_definition(definition)
        assert len(definition.resources) == 3
        customizer.gui.ui.taskNameLineEdit.setText("NEW NAME")
        definition2 = customizer._query_task_definition()
        assert definition2.task_name == "NEW NAME"
        file_dialog_mock.getOpenFileName.return_value = "/abc/def/ghi"
        customizer._choose_main_program_file_button_clicked()
        assert customizer.gui.ui.mainProgramFileLineEdit.text() == u"/abc/def/ghi"
        file_dialog_mock.getOpenFileName.return_value = ""
        customizer._choose_main_program_file_button_clicked()
        assert customizer.gui.ui.mainProgramFileLineEdit.text() == u"/abc/def/ghi"

        definition.task_type = "UNKNOWN"
        with self.assertLogs(logger, level="ERROR"):
            customizer._load_task_type(definition)

        options = GNROptions()
        customizer.set_options(options)
        assert customizer.logic.options == options
        assert customizer.get_options() == options
        assert isinstance(customizer.get_options(), GNROptions)

        customizer._RenderingNewTaskDialogCustomizer__test_task_button_clicked()
        customizer.test_task_computation_finished(True, 103139)
        assert customizer.task_state.definition.estimated_memory == 103139
        assert customizer.gui.ui.finishButton.isEnabled()
        customizer._show_add_resource_dialog()
        assert not customizer.gui.ui.finishButton.isEnabled()

        customizer._open_options()