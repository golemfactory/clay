from golem.config.active import ACTIVE_NET
from golem.monitor.serialization import defaultserializer
from .modelbase import BasicModel


class NodeMetadataModel(BasicModel):

    def __init__(self, client, os, ver):
        super(NodeMetadataModel, self).__init__(
            "NodeMetadata",
            client.session_id)

        self.os = os
        self.version = ver
        self.settings = defaultserializer.serialize("ClientConfigDescriptor",
                                                    client.config_desc)
        self.net = ACTIVE_NET


class NodeInfoModel(BasicModel):
    def __init__(self, sessid):
        super(NodeInfoModel, self).__init__("NodeInfo", sessid)
