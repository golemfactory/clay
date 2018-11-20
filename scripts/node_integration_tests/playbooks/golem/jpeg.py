from ..base import NodeTestPlaybook


class RegularRun(NodeTestPlaybook):
    provider_node_script = 'provider/debug'
    requestor_node_script = 'requestor/debug'
    task_settings = 'jpeg'
