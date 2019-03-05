from ..base import NodeTestPlaybook


class RegularRun(NodeTestPlaybook):
    provider_node_script = 'provider/debug'
    requestor_node_script = 'requestor/debug'

    provider_opts = {
        'min_price': 0,
    }
