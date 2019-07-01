from golem.config.active import EthereumConfig
from golem.monitor.serialization import defaultserializer
from .modelbase import BasicModel


class NodeMetadataModel(BasicModel):

    def __init__(self, client, os_info, ver):
        super(NodeMetadataModel, self).__init__(
            "NodeMetadata",
            client.get_key_id(),
            client.session_id)

        self.os_info = defaultserializer.serialize("OSInfo", os_info)
        self.settings = defaultserializer.serialize(
            "ClientConfigDescriptor",
            client.config_desc)
        self.version = ver
        self.net = EthereumConfig().ACTIVE_NET


class NodeInfoModel(BasicModel):
    def __init__(self, cliid, sessid):
        super(NodeInfoModel, self).__init__("NodeInfo", cliid, sessid)
