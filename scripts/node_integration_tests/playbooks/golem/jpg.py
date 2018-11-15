from ..base import NodeTestPlaybook

from apps.blender.task.blenderrendertask import BlenderTaskTypeInfo


class RegularRun(NodeTestPlaybook):
    provider_node_script = 'provider/debug'
    requestor_node_script = 'requestor/debug'
    task_settings = 'jpg'

    @property
    def output_extension(self):
        return BlenderTaskTypeInfo().output_formats[0]
