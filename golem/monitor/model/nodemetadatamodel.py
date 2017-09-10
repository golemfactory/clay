from golem.monitor.serialization import defaultserializer
from .modelbase import BasicModel


class NodeMetadataModel(BasicModel):

    def __init__(self, cliid, sessid, os, ver, settings):
        super(NodeMetadataModel, self).__init__("NodeMetadata", cliid, sessid)

        self.os = os
        self.version = ver
        self.settings = defaultserializer.serialize("ClientConfigDescriptor", settings)


class NodeInfoModel(BasicModel):
    def __init__(self, cliid, sessid):
        super(NodeInfoModel, self).__init__("NodeInfo", cliid, sessid)
