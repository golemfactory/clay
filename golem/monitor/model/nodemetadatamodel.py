from modelbase import BasicModel


class NodeMetadataModel(BasicModel):

    def __init__(self, cliid, sessid, os, ver):
        super(NodeMetadataModel, self).__init__("NodeMetadata")

        self.cliid      = cliid
        self.sessid     = sessid
        self.os         = os
        self.version    = ver
        self.settings   = ""
