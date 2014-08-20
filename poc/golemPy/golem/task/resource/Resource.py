import sys
import logging
sys.path.append('../../core/')

from golem.core.simplehash import SimpleHash

import os
from os.path import join, isdir, isfile
import zipfile

class TaskResourceHeader:

    ####################
    @classmethod
    def build( cls, relativeRoot, absoluteRoot ):
        return cls.__build( relativeRoot, absoluteRoot )

    ####################
    @classmethod
    def __build( cls, dirName, absoluteRoot, choosenFiles = None ):
        curTh = TaskResourceHeader( dirName )

        dirs  = [ name for name in os.listdir( absoluteRoot ) if os.path.isdir( os.path.join( absoluteRoot, name ) ) ]
        files = [ name for name in os.listdir( absoluteRoot ) if os.path.isfile( os.path.join( absoluteRoot, name ) ) ]

        filesData = []
        for f in files:
            hsh = SimpleHash.hash_file_base64( os.path.join( absoluteRoot, f ) )
            if choosenFiles and os.path.join( absoluteRoot, f ) not in  choosenFiles:
                continue

            filesData.append( ( f, hsh ) )

        #print "{}, {}, {}".format( relativeRoot, absoluteRoot, filesData )

        curTh.filesData = filesData

        subDirHeaders = []
        for d in dirs:
            childSubDirHeader = cls.__build( d, os.path.join( absoluteRoot, d ), choosenFiles)
            subDirHeaders.append( childSubDirHeader )

        curTh.subDirHeaders = subDirHeaders
        #print "{} {} {}\n".format( absoluteRoot, len( subDirHeaders ), len( filesData ) )

        return curTh

    ####################
    # Dodaje tylko te pola, ktorych nie ma w headerze (i/lub nie zgadzaj? si? hasze)
    @classmethod
    def buildHeaderDeltaFromHeader( cls, header, absoluteRoot, choosenFiles ):
        assert isinstance(header, TaskResourceHeader)

        curTr = TaskResourceHeader( header.dirName )

        dirs  = [ name for name in os.listdir( absoluteRoot ) if os.path.isdir( os.path.join( absoluteRoot, name ) ) ]
        files = [ name for name in os.listdir( absoluteRoot ) if os.path.isfile( os.path.join( absoluteRoot, name ) ) ]

        for d in dirs:
            if d in [ sdh.dirName for sdh in header.subDirHeaders ]:
                idx = [ sdh.dirName for sdh in header.subDirHeaders ].index( d )
                curTr.subDirHeaders.append( cls.buildHeaderDeltaFromHeader( header.subDirHeaders[ idx ], os.path.join( absoluteRoot, d ), choosenFiles ) )
            else:
                curTr.subDirHeaders.append( cls.__build( d, os.path.join( absoluteRoot, d ), choosenFiles ) )

        for f in files:
            fileHash = 0
            if f in [ file[ 0 ] for file in header.filesData ]:
                idx = [ file[ 0 ] for file in header.filesData ].index( f )
                fileHash = SimpleHash.hash_file_base64( os.path.join( absoluteRoot, f ) )

                if fileHash == header.filesData[ idx ][ 1 ]:
                    continue

            if choosenFiles and os.path.join( absoluteRoot, f ) not in  choosenFiles:
                continue

            if not fileHash:
                fileHash = SimpleHash.hash_file_base64( os.path.join( absoluteRoot, f ) )

            curTr.filesData.append( ( f, fileHash ) )

        return curTr

    ####################
    def __init__( self, dirName ):
        self.subDirHeaders  = []
        self.filesData      = []
        self.dirName        = dirName

    ####################
    def toString( self ):
        out = u"\nROOT '{}' \n".format( self.dirName )

        if len( self.subDirHeaders ) > 0:
            out += u"DIRS \n"
            for d in self.subDirHeaders:
                out += u"    {}\n".format( d.dirName )

        if len( self.filesData ) > 0:
            out += u"FILES \n"
            for f in self.filesData:
                out += u"    {} {}".format( f[ 0 ], f[ 1 ] )

        for d in self.subDirHeaders:
            out += d.toString()

        return out


    ####################
    def __str__( self ):
        return self.toString()

    ####################
    def hash( self ):
        return SimpleHash.hash_base64( self.toString().encode('utf-8') )

class TaskResource:

    ####################
    @classmethod
    def __build( cls, dirName, absoluteRoot ):
        curTh = TaskResource( dirName )

        dirs  = [ name for name in os.listdir( absoluteRoot ) if os.path.isdir( os.path.join( absoluteRoot, name ) ) ]
        files = [ name for name in os.listdir( absoluteRoot ) if os.path.isfile( os.path.join( absoluteRoot, name ) ) ]

        filesData = []
        for f in files:
            fileData = cls.readFile( os.path.join( absoluteRoot, f ) )
            hsh = SimpleHash.hash_base64( fileData )
            filesData.append( ( f, hsh, fileData ) )

        #print "{}, {}, {}".format( relativeRoot, absoluteRoot, filesData )

        curTh.filesData = filesData

        subDirResources = []
        for d in dirs:
            childSubDirHeader = cls.__build( d, os.path.join( absoluteRoot, d ) )
            subDirResources.append( childSubDirHeader )

        curTh.subDirResources = subDirResources
        #print "{} {} {}\n".format( absoluteRoot, len( subDirHeaders ), len( filesData ) )

        return curTh

    ####################
    @classmethod
    def readFile( cls, fileName ):
        try:
            f = open( fileName, "rb" )
            data = f.read()
        except Exception as ex:
            print ex
            return None

        return data

    ####################
    @classmethod
    def writeFile( cls, fileName, data ):
        try:
            f = open( fileName, "wb" )
            f.write( data )
        except Exception as ex:
            print ex

    ####################
    @classmethod
    def validateHeader( cls, header, absoluteRoot ):
        assert isinstance(header, TaskResourceHeader)

        for f in header.filesData:
            fname = os.path.join( absoluteRoot, f[ 0 ] ) 

            if not os.path.exists( fname ):
                return False, "File {} does not exist".format( fname )

            if not os.path.isfile( fname ):
                return False, "Entry {} is not a file".format( fname )

        for dh in header.subDirHeaders:
            validated, msg = cls.validateHeader( dh, os.path.join( absoluteRoot, dh.dirName ) )

            if not validated:
                return validated, msg

        return True, None

    ####################
    @classmethod
    def buildFromHeader( cls, header, absoluteRoot ):
        assert isinstance(header, TaskResourceHeader)

        curTr = TaskResource( header.dirName )

        filesData = []
        for f in header.filesData:
            fname = os.path.join( absoluteRoot, f[ 0 ] ) 
            fdata = cls.readFile( fname )
            
            if fdata is None:
                return None

            filesData.append( ( f[ 0 ], f[ 1 ], fdata ) )

        curTr.filesData = filesData

        subDirResources = []
        for sdh in header.subDirHeaders:
            subDirRes = cls.buildFromHeader( sdh, os.path.join( absoluteRoot, sdh.dirName ) )

            if subDirRes is None:
                return None
            
            subDirResources.append( subDirRes )

        curTr.subDirResources = subDirResources

        return curTr        

    ####################
    # Dodaje tylko te pola, ktorych nie ma w headerze (i/lub nie zgadzaj? si? hasze)
    @classmethod
    def buildDeltaFromHeader( cls, header, absoluteRoot ):
        assert isinstance(header, TaskResourceHeader)

        curTr = TaskResource( header.dirName )

        dirs  = [ name for name in os.listdir( absoluteRoot ) if os.path.isdir( os.path.join( absoluteRoot, name ) ) ]
        files = [ name for name in os.listdir( absoluteRoot ) if os.path.isfile( os.path.join( absoluteRoot, name ) ) ]

        for d in dirs:
            if d in [ sdh.dirName for sdh in header.subDirHeaders ]:
                idx = [ sdh.dirName for sdh in header.subDirHeaders ].index( d )
                curTr.subDirResources.append( cls.buildDeltaFromHeader( header.subDirHeaders[ idx ], os.path.join( absoluteRoot, d ) ) )
            else:
                curTr.subDirResources.append( cls.__build( d, os.path.join( absoluteRoot, d ) ) )

        for f in files:
            if f in [ file[ 0 ] for file in header.filesData ]:
                idx = [ file[ 0 ] for file in header.filesData ].index( f )
                if SimpleHash.hash_file_base64( os.path.join( absoluteRoot, f ) ) == header.filesData[ idx ][ 1 ]:
                    continue

            fdata = cls.readFile( os.path.join( absoluteRoot, f ) )
            
            if fdata is None:
                return None

            curTr.filesData.append( ( f, SimpleHash.hash_base64( fdata ), fdata ) )

        return curTr

    ####################
    def extract( self, toPath ):
        for dir in self.subDirResources:
            if not os.path.exists( os.path.join( toPath, dir.dirName ) ):
                os.makedirs( os.path.join( toPath, dir.dirName ) )

            dir.extract( os.path.join( toPath, dir.dirName ) )

        for f in self.filesData:
            if not os.path.exists( os.path.join( toPath, f[ 0 ] ) ) or SimpleHash.hash_file_base64( os.path.join( toPath, f[ 0 ] ) ) != f[ 1 ]:
                self.writeFile( os.path.join( toPath, f[ 0 ] ), f[ 2 ] )

    ####################
    def __init__( self, dirName ):
        self.filesData          = []
        self.subDirResources    = []
        self.dirName            = dirName

    ####################
    def toString( self ):
        out = "\nROOT '{}' \n".format( self.dirName )

        if len( self.subDirResources ) > 0:
            out += "DIRS \n"
            for d in self.subDirResources:
                out += "    {}\n".format( d.dirName )

        if len( self.filesData ) > 0:
            out += "FILES \n"
            for f in self.filesData:
                out += "    {:10} {} {}".format( len( f[ 2 ] ), f[ 0 ], f[ 1 ] )

        for d in self.subDirResources:
            out += d.toString()

        return out

    ####################
    def __str__( self ):
        return self.toString()

import unicodedata
import string

validFilenameChars = "-_.() %s%s" % (string.ascii_letters, string.digits)

def removeDisallowedFilenameChars(filename):
    cleanedFilename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore')
    return ''.join(c for c in cleanedFilename if c in validFilenameChars)

####################
def compressDir( rootPath, header, outputDir ):

    outputFile = removeDisallowedFilenameChars( header.hash().strip().decode( 'unicode-escape' ) + ".zip" )

    outputFile = os.path.join( outputDir, outputFile )

    zipf = zipfile.ZipFile( outputFile, 'w', compression = zipfile.ZIP_DEFLATED )

    currWorkingDir = os.getcwd()
    os.chdir( rootPath )
    logging.info("Working directory {}".format(os.getcwd()))

    try:
        compressDirImpl( "", header, zipf )

        zipf.close()
    finally:
        os.chdir( currWorkingDir )
        logging.info("Return to prev working directory {}".format(os.getcwd()))

    return outputFile

####################
def decompressDir( rootPath, zipFile ):

    zipf = zipfile.ZipFile( zipFile, 'r' )

    zipf.extractall( rootPath )

####################
def compressDirImpl( rootPath, header, zipf ):

    for sdh in header.subDirHeaders:
        compressDirImpl( os.path.join(rootPath, sdh.dirName), sdh, zipf )
        
    for fdata in header.filesData:
        zipf.write( os.path.join( rootPath, fdata[ 0 ] ) )

####################
def prepareDeltaZip( rootDir, header, outputDir, choosenFiles = None ):
    deltaHeader = TaskResourceHeader.buildHeaderDeltaFromHeader( header, rootDir, choosenFiles )
    return compressDir( rootDir, deltaHeader, outputDir )


if __name__ == "__main__":

    def walk_test( root ):
        for root, dirs, files in os.walk(root, topdown=True):
            for name in dirs:
                #print("D", os.path.join(root, name))
                print("D", root, name)
            #for name in files:
            #    print("F", os.path.join(root, name))

    def printAndPause( i ):
        import msvcrt as m
        def wait():
            m.getch()

        print "{}".format( i )
        wait()
    
    def main():
        t = TaskResourceHeader( "test", "resource_test_dir\\test" )
        print t
        t = 0

    import glob
    files = glob.glob( os.path.join( "input_64", "*.exr" ) )

    print files
    from golem.databuffer import DataBuffer

    db = DataBuffer()
    import gc
    while True:
        for f in files:
            if True:
                import cPickle
                import Compress
                from golem.Message import MessageTaskComputed, Message
                fh = open( f, 'rb' )
                printAndPause(0)
                fileData = Compress.compress( fh.read() )
                printAndPause(1)
                #fileData = fh.read()
                #data = cPickle.dumps( ( f, fileData ) )
                data = fileData
                printAndPause(2)
                m = MessageTaskComputed( "", {}, data )
                printAndPause(3)
                serializedMess = m.serializeWithHeader()
                printAndPause(4)
                db.appendString(serializedMess)
                printAndPause(5)
                desMess = Message.deserialize( db )       
                printAndPause(6)
                data = desMess[0].result
                printAndPause(7)
                #( name, data ) = cPickle.loads( desMess[0].result )
                d = Compress.decompress( data )
                printAndPause(8)
                out = open("resdupa", 'wb' )
                printAndPause(9)
                out.write( d )
                printAndPause(10)
                out.close()
                printAndPause(11)
            
            gc.collect()
            printAndPause(12)

        #tr = pickle.loads( trp )
        #fh = open( os.path.join( tmpDir, tr[ 0 ] ), "wb" )
        #fh.write( decompress( tr[ 1 ] ) )
        #fh.close()

    #th = TaskResourceHeader.build( "test", "resource_test_dir\\test_empty" )

    #prepareDeltaZip( "resource_test_dir\\test", th, "resource_test_dir.zip" )

    #print th
    
    #print "Entering task testing zone"
    #v, m = TaskResource.validateHeader( th, "resource_test_dir\\test"  )

    #if not v:
    #    print m
    #else:
    #    tr = TaskResource.buildFromHeader( th, "resource_test_dir\\test" )
    #    print tr

    #    trd = TaskResource.buildDeltaFromHeader( th, "resource_test_dir\\test" )

    #    trd.extract( "out" )

    #    save( trd, "trd.zip" )

    #    loadedTrd = load( "trd.zip" )
    #    print trd

    #    loadedTrd.extract( "out" )

        

    #walk_test( "." )
    #main()
