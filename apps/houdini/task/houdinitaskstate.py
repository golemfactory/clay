from apps.core.task.coretaskstate import (TaskDefinition, TaskDefaults, Options)

from apps.houdini.houdinienvironment import HoudiniEnvironment
from golem.resource.dirmanager import list_dir_recursive

import os



class HoudiniTaskDefaults(TaskDefaults):

    def __init__(self):
        self.main_program_file = HoudiniEnvironment().main_program_file
        self.min_subtasks = 1
        self.max_subtasks = 10000
        self.default_subtasks = 6



class HoudiniTaskDefinition(TaskDefinition):
    def __init__(self, defaults=None):
        TaskDefinition.__init__(self)

        self.options = HoudiniTaskOptions()
        self.task_type = 'HOUDINI'
        self.output_path = ""


    def is_valid(self):
        return super(TaskDefinition, self).is_valid()


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
        render_params = task_definition_dict["options"][ "render_params" ]

        self.scene_file = render_params["scene_file"]
        self.render_node = render_params["render_node"]
        self.start_frame = int(render_params["start_frame"])
        self.end_frame = int(render_params["end_frame"])

    def build_dict( self ):

        opts = dict()

        opts["scene_file"] = self.scene_file
        opts["render_node"] = self.render_node
        opts["start_frame"] = self.start_frame
        opts["end_frame"] = self.end_frame
        opts["output_file"] = self.output_file

        return opts


