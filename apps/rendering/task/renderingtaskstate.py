from os import path

from apps.core.task.coretaskstate import (TaskDefinition,
                                          AdvanceVerificationOptions,
                                          CoreTaskDefaults)


class RendererDefaults(CoreTaskDefaults):
    """ Suggested default values for Rendering tasks"""
    def __init__(self):
        super(RendererDefaults, self).__init__()
        self.resolution = [1920, 1080]
        self._pixel_to_seconds = 384

    @property
    def subtask_timeout(self):
        return self.resolution[0] * self.resolution[1] / self._pixel_to_seconds

    @property
    def full_task_timeout(self):
        return self.subtask_timeout * self.default_subtasks


class RenderingTaskDefinition(TaskDefinition):
    def __init__(self):
        TaskDefinition.__init__(self)
        self.resolution = [0, 0]
        self.renderer = None
        self.options = None
        self.main_scene_file = ""
        self.output_format = ""

    def is_valid(self):
        is_valid, err = super(RenderingTaskDefinition, self).is_valid()
        if is_valid and not path.exists(self.main_scene_file):
            return False, u"Main scene file {} is not properly set".format(
                self.main_scene_file)
        return is_valid, err

    def add_to_resources(self):
        super(RenderingTaskDefinition, self).add_to_resources()
        self.resources.add(path.normpath(self.main_scene_file))

    def make_preset(self):
        """ Create preset that can be shared with different tasks
        :return dict:
        """
        preset = super(RenderingTaskDefinition, self).make_preset()
        preset["resolution"] = self.resolution
        preset["output_format"] = self.output_format
        return preset

    def load_preset(self, preset):
        """ Apply options from preset to this task definition
        :param dict preset: Dictionary with shared options
        """
        super(RenderingTaskDefinition, self).load_preset(preset)
        self.resolution = preset["resolution"]
        self.output_format = preset["output_format"]


class AdvanceRenderingVerificationOptions(AdvanceVerificationOptions):
    def __init__(self):
        AdvanceVerificationOptions.__init__(self)
        self.box_size = (5, 5)
        self.probability = 0.01
