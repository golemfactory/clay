import from apps.core.task.coretaskstate import (TaskDefinition, TaskDefaults, Options)

import from apps.houdini.houdinienvironment import HoudiniEnvironment
from golem.resource.dirmanager import list_dir_recursive

import os



class HoudiniTaskDefaults(TaskDefaults):

    def __init__(self):
        pass



class HoudiniTaskDefinition(TaskDefinition):
    def __init__(self, defaults=None):
        TaskDefinition.__init__(self)

        self.options = HoudiniTaskOptions()
        self.task_type = 'HOUDINI'


    def is_valid(self):
        is_valid, err = super(TaskDefinition, self).is_valid()
        if is_valid and not os.path.exists(self.self.options.scene_file):
            return False, "Main scene file {} is not properly set".format(
                self.options.scene_file)
        return is_valid, err


    def add_to_resources(self):
        super(HoudiniTaskDefinition, self).add_to_resources()

        scene_file_path = self.options.scene_file
        assets_dir = os.path.dirname( scene_file_path )

        self.resources = set(list_dir_recursive(assets_dir))


class HoudiniTaskOptions(Options):


    def __init__(self):
        super(HoudiniTaskOptions, self).__init__()

        self.environment = HoudiniEnvironment()

        self.scene_file = ""                    # .hip file name
        self.render_node = ""                   # for example: /out/mantra_ipr
        self.start_frame = 0
        self.end_frame = 0
        self.output_file = "output-$F4.png"     # output defined in base class


    def build_from_dictionary( self, task_definition_dict ):

        # dictionary comes from GUI
        opts = task_definition_dict["options"]

        self.scene_file = opts["scene_file"]
        self.render_node = opts["render_node"]
        self.start_frame = int(opts["start_frame"])
        self.end_frame = int(opts["end_frame"])

    def build_dict( self ):

        opts = dict()

        opts["scene_file"] = self.scene_file
        opts["render_node"] = self.render_node
        opts["start_frame"] = self.start_frame
        opts["end_frame"] = self.end_frame

        return opts


