from ..base import NodeTestPlaybook


class ZeroPrice(NodeTestPlaybook):
    provider_node_script = 'provider/debug'
    requestor_node_script = 'requestor/debug'

    provider_opts = {
        'min_price': 0,
    }
    requestor_opts = {
        'max_price': 0,
    }

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.task_dict['bid'] = 0
