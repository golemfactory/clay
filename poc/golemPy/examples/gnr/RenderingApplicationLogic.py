import logging
import os

from examples.gnr.GNRApplicationLogic import GNRApplicationLogic
from examples.gnr.RenderingTaskState import RenderingTaskState

logger = logging.getLogger(__name__)


class AbsRenderingApplicationLogic(object):
    def __init__(self):
        self.renderers = {}
        self.current_renderer = None
        self.default_renderer = None

    def get_renderers(self):
        return self.renderers

    def get_renderer(self, name):
        if name in self.renderers:
            return self.renderers[name]
        else:
            assert False, "Renderer {} not registered".format(name)

    def get_default_renderer(self):
        return self.default_renderer

    def register_new_renderer_type(self, renderer):
        if renderer.name not in self.renderers:
            self.renderers[renderer.name] = renderer
            if len(self.renderers) == 1:
                self.default_renderer = renderer
        else:
            assert False, "Renderer {} already registered".format(renderer.name)

    def set_current_renderer(self, rname):
        if rname in self.renderers:
            self.current_renderer = self.renderers[rname]
        else:
            assert False, "Unreachable"

    def get_current_renderer(self):
        return self.current_renderer

    def _get_new_task_state(self):
        return RenderingTaskState()

    def _get_builder(self, task_state):
        return self.renderers[task_state.definition.renderer].task_builder_type(self.client.get_id(),
                                                                                task_state.definition,
                                                                                self.client.get_root_path())

    def _validate_task_state(self, task_state):

        td = task_state.definition
        if td.renderer in self.renderers:

            if not os.path.exists(td.main_program_file):
                self._show_error_window("Main program file does not exist: {}".format(td.main_program_file))
                return False

            if not self.__check_output_file(td.output_file):
                return False

            if not os.path.exists(td.main_scene_file):
                self._show_error_window("Main scene file is not properly set")
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
            self._show_error_window("Cannot open file: {}".format(output_file))
            return False
        except:
            self._show_error_window("Output file is not properly set")
            return False


class RenderingApplicationLogic(AbsRenderingApplicationLogic, GNRApplicationLogic):
    def __init__(self):
        GNRApplicationLogic.__init__(self)
        AbsRenderingApplicationLogic.__init__(self)
