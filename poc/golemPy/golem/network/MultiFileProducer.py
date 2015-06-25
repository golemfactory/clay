import logging
import os
import struct

from golem.core.variables import BUFF_SIZE

logger = logging.getLogger(__name__)

#########################################################
class MultiFileProducer:
    ###################
    def __init__(self, fileList, session, buffSize = BUFF_SIZE, extraData = None):
        self.fileList = fileList
        self.session = session
        self.buffSize = buffSize
        self.extraData = extraData
        self.fh = None
        self.initData()
        self.register()

    ###################
    def initData(self):
        if len(self.fileList) == 0:
            logger.warning("Empty file list to send")
            self.data = None
            return
        self.fh = open(self.fileList[-1], 'rb')
        self.size = os.path.getsize(self.fileList[-1])
        logger.info("Sendig file {}, size:{}".format(self.fileList[-1], self.size))
        self._prepareInitData()

    ###################
    def register(self):
        self.session.conn.transport.registerProducer(self, False)

    ###################
    def resumeProducing(self):
        if self.data:
            self.session.conn.transport.write(self.data)
            self._printProgress()
            self._prepareData()
        elif len(self.fileList) > 1:
            if self.fh is not None:
                self.fh.close()
            self.fileList.pop()
            self.initData()
            self.resumeProducing()
        else:
            if self.fh is not None:
                self.fh.close()
            self.session.dataSent(self.extraData)
            self.session.conn.transport.unregisterProducer()

    ###################
    def stopProducing(self):
        pass

    ###################
    def clean(self):
        if self.fh is not None:
            self.fh.close()

    ###################
    def _prepareInitData(self):
        self.data = struct.pack("!L", self.size) + self.fh.read(self.buffSize)

    ###################
    def _prepareData(self):
        self.data = self.fh.read(self.buffSize)

    ###################
    def _printProgress(self):
        print "\rSending progress {} %                       ".format(int(100 * float(self.fh.tell()) / self.size)),

#########################################################
class EncryptMultiFileProducer(MultiFileProducer):
    ###################
    def _prepareInitData(self):
        data = self.session.encrypt(self.fh.read(self.buffSize))
        self.data = struct.pack("!L", self.size) + struct.pack("!L", len(data)) + data

    ###################
    def _prepareData(self):
        data = self.fh.read(self.buffSize)
        if data:
            data = self.session.encrypt(data)
            self.data = struct.pack("!L", len(data)) + data
        else:
            self.data = ''