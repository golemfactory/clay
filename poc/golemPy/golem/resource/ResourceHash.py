import os
import hashlib
import base64

class ResourceHash:
    ##################################
    def __init__(self, resourceDir):
        self.resourceDir = resourceDir

    ##################################
    def splitFile(self, filename, blockSize = 2 ** 20):
        with open(filename, "rb") as f:
            fileList = []
            while True:
                data = f.read(blockSize)
                if not data:
                    break


                filehash = os.path.join(self.resourceDir, self.__count_hash(data))
                filehash = os.path.normpath(filehash)

                with open(filehash, "wb") as fwb:
                    fwb.write(data)

                fileList.append(filehash)
        return fileList

    ##################################
    def connectFiles(self, fileList, resFile):
        with open(resFile, 'wb') as f:
            for file_hash in fileList:
                with open(file_hash, "rb") as fh:
                    while True:
                        data = fh.read()
                        if not data:
                            break
                        f.write(data)

    ##################################
    def getFileHash(self, filename):
        with open(filename, "rb") as f:
            data = f.read()
            hash = self.__count_hash(data)
        return hash

    ##################################
    def set_resource_dir(self, resourceDir):
        self.resourceDir = resourceDir

    ##################################
    def __count_hash(self, data):
            sha = hashlib.sha1()
            sha.update(data)
            return base64.urlsafe_b64encode(sha.digest())