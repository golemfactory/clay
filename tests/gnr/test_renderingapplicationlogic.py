#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import uuid
from mock import Mock

from PyQt4.QtCore import Qt
from PyQt4.QtTest import QTest

from apps.blender.benchmark.benchmark import BlenderBenchmark
from gui.startapp import register_rendering_task_types

from gnr.application import GNRGui
from gnr.customizers.renderingmainwindowcustomizer import RenderingMainWindowCustomizer
from gnr.renderingapplicationlogic import RenderingApplicationLogic
from gnr.renderingtaskstate import RenderingTaskState
from gnr.ui.appmainwindow import AppMainWindow
from golem.resource.dirmanager import DirManager
from golem.tools.testwithreactor import TestDirFixtureWithReactor


class TestRenderingApplicationLogic(TestDirFixtureWithReactor):

    def setUp(self):
        super(TestDirFixtureWithReactor, self).setUp()
        self.logic = RenderingApplicationLogic()
        self.logic.datadir = self.path
        self.gnrgui = GNRGui(self.logic, AppMainWindow)
        self.logic.customizer = RenderingMainWindowCustomizer(self.gnrgui.main_window, self.logic)
        self.logic.dir_manager = DirManager(self.path)

    def tearDown(self):
        super(TestDirFixtureWithReactor, self).tearDown()
        self.gnrgui.app.exit(0)
        self.gnrgui.app.deleteLater()

    def test_change_verification_options(self):
        logic = self.logic
        logic.client = Mock()
        logic.client.datadir = self.path
        prev_y = logic.customizer.gui.ui.verificationSizeYSpinBox.maximum()
        logic.change_verification_option(size_x_max=914)
        assert logic.customizer.gui.ui.verificationSizeXSpinBox.maximum() == 914
        assert logic.customizer.gui.ui.verificationSizeYSpinBox.maximum() == prev_y
        logic.change_verification_option(size_y_max=123)
        assert logic.customizer.gui.ui.verificationSizeXSpinBox.maximum() == 914
        assert logic.customizer.gui.ui.verificationSizeYSpinBox.maximum() == 123
        logic.change_verification_option(size_y_max=3190, size_x_max=134)
        assert logic.customizer.gui.ui.verificationSizeXSpinBox.maximum() == 134
        assert logic.customizer.gui.ui.verificationSizeYSpinBox.maximum() == 3190

    def test_messages(self):
        logic = self.logic
        logic.customizer = RenderingMainWindowCustomizer(self.gnrgui.main_window, logic)
        rts = RenderingTaskState()
        logic._validate_task_state(rts)
        register_rendering_task_types(logic)
        m = Mock()
        logic.run_benchmark(BlenderBenchmark(), m, m)
        if logic.br.tt:
            logic.br.tt.join()
        assert logic.progress_dialog_customizer.gui.ui.message.text() == u"Recounted"
        assert logic.progress_dialog_customizer.gui.ui.okButton.isEnabled()
        assert logic.customizer.gui.ui.recountBlenderButton.isEnabled()
        assert logic.customizer.gui.ui.recountButton.isEnabled()
        assert logic.customizer.gui.ui.recountLuxButton.isEnabled()
        assert logic.customizer.gui.ui.settingsOkButton.isEnabled()
        assert logic.customizer.gui.ui.settingsCancelButton.isEnabled()
        QTest.mouseClick(logic.progress_dialog_customizer.gui.ui.okButton, Qt.LeftButton)

        broken_benchmark = BlenderBenchmark()
        broken_benchmark.task_definition.main_program_file = u'Bździągwa'
        logic.show_error_window = Mock()
        logic.run_benchmark(broken_benchmark, m, m)
        if logic.br.tt:
            logic.br.tt.join()
        logic.show_error_window.assert_called_with(u"Main program file does not exist: Bździągwa")

        broken_benchmark = BlenderBenchmark()
        broken_benchmark.task_definition.output_file = u'/x/y/Bździągwa'
        logic.run_benchmark(broken_benchmark, m, m)
        if logic.br.tt:
            logic.br.tt.join()
        logic.show_error_window.assert_called_with(u"Cannot open output file: /x/y/Bździągwa")

        broken_benchmark = BlenderBenchmark()
        broken_benchmark.task_definition.main_scene_file = "NOT EXISTING"
        broken_benchmark.task_definition.output_file = os.path.join(self.path, str(uuid.uuid4()))
        logic.run_benchmark(broken_benchmark, m, m)
        if logic.br.tt:
            logic.br.tt.join()
        logic.show_error_window.assert_called_with(u"Main scene file is not properly set")

        logic.test_task_computation_error(u"Bździągwa")
        logic.progress_dialog_customizer.gui.ui.message.text() == u"Task test computation failure. Bździągwa"
        logic.test_task_computation_error(u"500 server error")
        logic.progress_dialog_customizer.gui.ui.message.text() ==\
        u"Task test computation failure. [500 server error] There is a chance that you RAM limit is too low. Consider increasing max memory usage"
        logic.test_task_computation_error(None)
        logic.progress_dialog_customizer.gui.ui.message.text() == u"Task test computation failure. "
        logic.test_task_computation_success([], 10000)
        logic.progress_dialog_customizer.gui.ui.message.text() == u"Task task computation success!"
