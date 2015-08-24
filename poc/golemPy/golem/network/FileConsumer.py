import struct
import os

from golem.core.variables import LONG_STANDARD_SIZE

class FileConsumer:
    ###################
    def __init__(self, tmpFile, outputDir, session, extraData):
        self.fh = None
        self.fileSize = -1
        self.recvSize = 0

        self.tmpFile = tmpFile
        self.outputDir = outputDir

        self.session = session
        self.extraData = extraData

        self.lastPercent = 0

    ###################
    def dataReceived(self, data):
        locData = data
        if self.fileSize == -1:
            locData = self._getFirstChunk(data)

        assert self.fh

        self.recvSize += len(locData)
        self.fh.write(locData)

        self._printProgress()

        if self.recvSize == self.fileSize:
            self._endReceiving()

    ###################
    def close(self):
        if self.fh is not None:
            self.fh.close()
            self.fh = None
            if self.recvSize != self.fileSize:
                os.remove(self.tmpFile)

    ###################
    def _getFirstChunk(self, data):
        self.lastPercent = 0
        (self.fileSize,) = struct.unpack("!L", data[ :LONG_STANDARD_SIZE ])
        assert self.fh is None

        self.fh = open(self.tmpFile, 'wb')
        return  data[ LONG_STANDARD_SIZE: ]

    ###################
    def _printProgress(self):
        if self.fileSize > 0:
            prct = int(100 * self.recvSize / float(self.fileSize))
            if prct > self.lastPercent:
                print "\rFile data receving {} %                       ".format( prct),
                self.lastPercent = prct

    ###################
    def _endReceiving(self):
        self.session.conn.file_mode = False
        self.fh.close()
        self.fh = None
        self.extraData['fileSize'] = self.fileSize
        self.extraData['outputDir'] = self.outputDir
        self.extraData['tmpFile'] = self.tmpFile
        self.session.fullFileReceived(self.extraData)
        self.fileSize = -1
        self.recvSize = 0

#########################################################
class DecryptFileConsumer(FileConsumer):
    ###################
    def __init__(self, tmpFile, outputDir, session, extraData):
        self.chunkSize = 0
        self.recvChunSize = 0
        self.lastData = ''
        FileConsumer.__init__(self, tmpFile, outputDir, session, extraData)


    ###################
    def dataReceived(self, data):
        locData = self.lastData + data
        if self.fileSize == -1:
            locData = self._getFirstChunk(data)

        assert self.fh

        receiveNext = False
        while not receiveNext:
            if self.chunkSize == 0:
                (self.chunkSize,) = struct.unpack("!L", locData[ :LONG_STANDARD_SIZE ])
                locData = locData[LONG_STANDARD_SIZE:]

            self.recvChunkSize = len(locData)
            if self.recvChunkSize >= self.chunkSize:
                data = self.session.decrypt(locData[:self.chunkSize])
                self.fh.write(data)
                self.recvSize += len(data)
                self.lastData = locData[self.chunkSize:]
                self.recvChunkSize = 0
                self.chunkSize = 0
                locData = self.lastData

                if len(self.lastData) <= LONG_STANDARD_SIZE:
                    receiveNext = True
            else:
                self.lastData = locData
                receiveNext = True

            self._printProgress()

            if self.recvSize >= self.fileSize:
                self._endReceiving()
                receiveNext = True