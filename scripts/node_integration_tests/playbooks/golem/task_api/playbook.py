from apps.blender.resources.images.entrypoints.scripts.verifier_tools\
    .file_extension import matcher
from ...base import NodeTestPlaybook


class Playbook(NodeTestPlaybook):
    @property
    def output_extension(self):
        extension = super().output_extension
        return matcher.get_expected_extension(extension)
