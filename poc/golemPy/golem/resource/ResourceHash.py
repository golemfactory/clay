import os
import hashlib
import base64

class ResourceHash:
    ##################################
    def __init__( self, resourceDir ):
        self.resourceDir = resourceDir

    ##################################
    def splitFile( self, filename, blockSize = 2 ** 20 ):
        with open( filename, "rb") as f:
            fileList = []
            while True:
                data = f.read( blockSize )
                if not data:
                    break

                sha = hashlib.sha1()
                sha.update( data )

                filehash = os.path.join( self.resourceDir, base64.urlsafe_b64encode( sha.digest() ) )
                filehash = os.path.normpath( filehash )

                with open( filehash, "wb") as fwb:
                    fwb.write( data )

                fileList.append( filehash )
        return fileList

    ##################################
    def connectFiles( self, fileList, resFile ):
        with open( resFile, 'wb' ) as f:
            for fileHash in fileList:
                with open( fileHash, "rb" ) as fh:
                    while True:
                        data = fh.read()
                        if not data:
                            break
                        f.write( data )