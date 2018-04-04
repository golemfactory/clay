from golem.monitor.serialization import defaultserializer
from .modelbase import BasicModel


class NodeMetadataModel(BasicModel):

    def __init__(self, client, os, ver):
        super(NodeMetadataModel, self).__init__(
            "NodeMetadata",
            client.get_key_id(),
            client.session_id)

        self.os = os
        self.version = ver
        self.settings = defaultserializer.serialize("ClientConfigDescriptor",
                                                    client.config_desc)
        self.net = 'mainnet' if client.mainnet else 'testnet'


class NodeInfoModel(BasicModel):
    def __init__(self, cliid, sessid):
        super(NodeInfoModel, self).__init__("NodeInfo", cliid, sessid)
