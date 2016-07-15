from modelbase import BasicModel
from golem.monitor.serialization.defaultserializer import DefaultSerializer


class NodeMetadataModel(BasicModel):

    def __init__(self, cliid, sessid, os, ver, settings):
        super(NodeMetadataModel, self).__init__("NodeMetadata")

        self.cliid = cliid
        self.sessid = sessid
        self.os = os
        self.version = ver
        self.settings = DefaultSerializer.serialize("ClientConfigDescriptor", settings)
