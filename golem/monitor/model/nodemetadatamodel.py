from modelbase import BasicModel
from golem.monitor.serialization.defaultserializer import DefaultSerializer


class NodeMetadataModel(BasicModel):

    def __init__(self, cliid, sessid, os, ver, description, settings):
        super(NodeMetadataModel, self).__init__("NodeMetadata")

        self.cliid = cliid
        self.sessid = sessid
        self.os = os
        self.version = ver
        self.description = description
        self.settings = DefaultSerializer.serialize("ClientConfigDescriptor", settings)


class NodeInfoModel(BasicModel):
    def __init__(self, cliid, sessid):
        super(NodeInfoModel, self).__init__("NodeInfo")
        self.cliid = cliid
        self.sessid = sessid
