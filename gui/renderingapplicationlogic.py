import logging
import os

from apps.rendering.task.renderingtaskstate import RenderingTaskState

from gui.applicationlogic import GNRApplicationLogic

logger = logging.getLogger("app")


class RenderingApplicationLogic(GNRApplicationLogic):
    def __init__(self):
        GNRApplicationLogic.__init__(self)
        self.options = None

    def change_verification_option(self, size_x_max=None, size_y_max=None):
        if size_x_max:
            self.customizer.gui.ui.verificationSizeXSpinBox.setMaximum(size_x_max)
        if size_y_max:
            self.customizer.gui.ui.verificationSizeYSpinBox.setMaximum(size_y_max)

    def _get_new_task_state(self):
        return RenderingTaskState()

    def _validate_task_state(self, task_state):

        td = task_state.definition
        if td.task_type in self.task_types:

            if not os.path.exists(td.main_program_file):
                self.customizer.show_error_window(u"Main program file does not exist: {}".format(td.main_program_file))
                return False

            if not self.__check_output_file(td.output_file):
                return False

            if not os.path.exists(td.main_scene_file):
                self.customizer.show_error_window(u"Main scene file is not properly set")
                return False
        else:
            return False

        return True

    def __check_output_file(self, output_file):
        try:
            file_exist = os.path.exists(output_file)

            with open(output_file, 'a'):
                pass
            if not file_exist:
                os.remove(output_file)
            return True
        except IOError:
            self.customizer.show_error_window(u"Cannot open output file: {}".format(output_file))
            return False
        except (OSError, TypeError) as err:
            self.customizer.show_error_window(u"Output file {} is not properly set: {}".format(output_file, err))
            return False