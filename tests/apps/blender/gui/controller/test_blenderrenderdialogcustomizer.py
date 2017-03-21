import unittest

from mock import Mock, patch, ANY

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.tools.testdirfixture import TestDirFixture

from apps.blender.gui.controller.blenderrenderdialogcustomizer import BlenderRenderDialogCustomizer
from apps.blender.gui.view.gen.ui_BlenderWidget import Ui_BlenderWidget
from apps.blender.task.blenderrendertask import BlenderTaskTypeInfo
from apps.rendering.gui.controller.renderercustomizer import FrameRendererCustomizer
from gui.controller.mainwindowcustomizer import MainWindowCustomizer

from gui.application import Gui
from gui.applicationlogic import GuiApplicationLogic
from gui.view.appmainwindow import AppMainWindow
from gui.view.widget import TaskWidget


class TestFramesConversion(unittest.TestCase):
    def test_frames_to_string(self):
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string([1, 4, 3, 2]), "1-4")
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string([1]), "1")
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string(range(10)), "0-9")
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string(range(13, 16) + range(10)), "0-9;13-15")
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string([1, 3, 4, 5, 10, 11]), '1;3-5;10-11')
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string([0, 5, 10, 15]), '0;5;10;15')
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string([]), "")
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string(["abc", "5"]), "")
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string(["1", "5"]), "1;5")
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string(["5", "2", "1", "3"]), "1-3;5")
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string([-1]), "")
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string([2, 3, -1]), "")
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string("ABC"), "")

    def test_string_to_frames(self):
        self.assertEqual(BlenderRenderDialogCustomizer.string_to_frames('1-4'), range(1, 5))
        self.assertEqual(BlenderRenderDialogCustomizer.string_to_frames('5-8;1-3'), [1, 2, 3, 5, 6, 7, 8])
        self.assertEqual(BlenderRenderDialogCustomizer.string_to_frames('1 - 4'), range(1, 5))
        self.assertEqual(BlenderRenderDialogCustomizer.string_to_frames('0-9; 13-15'), range(10) + range(13, 16))
        self.assertEqual(BlenderRenderDialogCustomizer.string_to_frames('0-15,5;23'), [0, 5, 10, 15, 23])
        self.assertEqual(BlenderRenderDialogCustomizer.string_to_frames('0-15,5;23-25;26'),
                         [0, 5, 10, 15, 23, 24, 25, 26])
        self.assertEqual(BlenderRenderDialogCustomizer.string_to_frames('abc'), [])
        self.assertEqual(BlenderRenderDialogCustomizer.string_to_frames('0-15,5;abc'), [])
        self.assertEqual(BlenderRenderDialogCustomizer.string_to_frames(0), [])
        self.assertEqual(BlenderRenderDialogCustomizer.string_to_frames('5-8;1-2-3'), [])
        self.assertEqual(BlenderRenderDialogCustomizer.string_to_frames('1-100,2,3'), [])


class TestBlenderRenderDialogCustomizer(TestDirFixture):

    def setUp(self):
        super(TestBlenderRenderDialogCustomizer, self).setUp()
        self.logic = GuiApplicationLogic()
        self.gui = Gui(Mock(), AppMainWindow)

    def tearDown(self):
        super(TestBlenderRenderDialogCustomizer, self).tearDown()
        self.gui.app.exit(0)
        self.gui.app.deleteLater()

    @patch("gui.controller.customizer.QMessageBox")
    def test_blender_customizer(self, mock_messagebox):
        self.logic.customizer = MainWindowCustomizer(self.gui.main_window,
                                                     self.logic)
        self.logic.register_new_task_type(
            BlenderTaskTypeInfo(TaskWidget(Ui_BlenderWidget),
                                BlenderRenderDialogCustomizer))
        self.logic.client = Mock()
        self.logic.client.config_desc = ClientConfigDescriptor()
        self.logic.client.config_desc.use_ipv6 = False
        self.logic.client.config_desc.max_price = 0
        self.logic.client.get_config.return_value = self.logic.client.config_desc
        self.logic.client.get_res_dirs.return_value = {'computing': self.path, 'received': self.path}
        self.logic.customizer.init_config()
        customizer = self.logic.customizer.new_task_dialog_customizer.task_customizer

        assert isinstance(customizer, FrameRendererCustomizer)
        assert not customizer.gui.ui.framesCheckBox.isChecked()
        customizer._change_options()
        assert customizer.options.frames == range(1, 11)
        customizer.gui.ui.framesCheckBox.setChecked(True)
        customizer.gui.ui.framesLineEdit.setText(u"{}".format("1;3;5-12"))
        customizer._change_options()
        assert customizer.options.frames == [1, 3] + range(5, 13)
        customizer.gui.ui.framesLineEdit.setText(u"{}".format("Not proper frames"))
        customizer._change_options()
        assert customizer.options.frames == [1, 3] + range(5, 13)
        mock_messagebox.assert_called_with(mock_messagebox.Critical, "Error",
                                           u"Wrong frame format. Frame list expected, e.g. 1;3;5-12.",
                                           ANY, ANY)
