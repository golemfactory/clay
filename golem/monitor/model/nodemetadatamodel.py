import json

from golem.config.active import EthereumConfig
from .modelbase import BasicModel


class NodeMetadataModel(BasicModel):

    def __init__(self, client, os_info, ver):
        super(NodeMetadataModel, self).__init__(
            "NodeMetadata",
            client.get_key_id(),
            client.session_id)

        # FIXME Remove double jsonification.
        # This model will be put through json.dumps().
        # There is no need to dumps os_info & settings
        self.os_info = json.dumps({
            'type': "OSInfo",
            'obj': os_info.__dict__,
        })
        self.settings = json.dumps({
            'type': "ClientConfigDescriptor",
            'obj': client.config_desc.__dict__,
        })
        self.version = ver
        self.net = EthereumConfig().ACTIVE_NET


class NodeInfoModel(BasicModel):
    def __init__(self, cliid, sessid):
        super(NodeInfoModel, self).__init__("NodeInfo", cliid, sessid)
