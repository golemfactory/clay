from ...base import NodeTestPlaybook

from apps.blender.task.blenderrendertask import BlenderTaskTypeInfo


class Playbook(NodeTestPlaybook):
    @property
    def output_extension(self):
        return BlenderTaskTypeInfo().output_formats[0]
