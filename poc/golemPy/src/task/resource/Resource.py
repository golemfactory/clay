import sys
sys.path.append('../../core/')

from simplehash import SimpleHash

import os
from os.path import join, isdir, isfile

class TaskResourceHeader:

    ####################
    @classmethod
    def build( cls, root ):
        return cls.__build( root, root )

    ####################
    @classmethod
    def __build( cls, relativeRoot, absoluteRoot ):
        curTh = TaskResourceHeader( relativeRoot, absoluteRoot )

        dirs  = [ ( name, os.path.join( absoluteRoot, name ) ) for name in os.listdir( absoluteRoot ) if os.path.isdir( os.path.join( absoluteRoot, name ) ) ]
        files = [ name for name in os.listdir( absoluteRoot ) if os.path.isfile( os.path.join( absoluteRoot, name ) ) ]

        filesData = []
        for f in files:
            hsh = SimpleHash.hash_file_base64( os.path.join( absoluteRoot, f ) )
            filesData.append( ( f, hsh ) )

        #print "{}, {}, {}".format( relativeRoot, absoluteRoot, filesData )

        curTh.filesData = filesData

        subDirHeaders = []
        for d in dirs:
            childSubDirHeader = cls.__build( d[ 0 ], d[ 1 ] )
            subDirHeaders.append( childSubDirHeader )

        curTh.subDirHeaders = subDirHeaders
        #print "{} {} {}\n".format( absoluteRoot, len( subDirHeaders ), len( filesData ) )

        return curTh

    ####################
    def __init__( self, relativePath, absolutePath ):
        self.subDirHeaders  = []
        self.filesData      = []
        self.relativePath   = relativePath
        self.absolutePath   = absolutePath

    ####################
    def toString( self ):
        out = "\nROOT '{}' \n".format( self.absolutePath )

        if len( self.subDirHeaders ) > 0:
            out += "DIRS \n"
            for d in self.subDirHeaders:
                out += "    {}\n".format( d.relativePath )

        if len( self.filesData ) > 0:
            out += "FILES \n"
            for f in self.filesData:
                out += "    {} {}".format( f[ 0 ], f[ 1 ] )

        for d in self.subDirHeaders:
            out += d.toString()

        return out


    ####################
    def __str__( self ):
        return self.toString()

class TaskResource:

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
    def validateHeader( cls, header ):
        assert isinstance(header, TaskResourceHeader)

        for f in header.filesData:
            fname = os.path.join( header.absolutePath, f[ 0 ] ) 

            if not os.path.exists( fname ):
                return False, "File {} does not exist".format( fname )

            if not os.path.isfile( fname ):
                return False, "Entry {} is not a file".format( fname )

        for dh in header.subDirHeaders:
            validated, msg = cls.validateHeader( dh )

            if not validated:
                return validated, msg

        return True, None

    ####################
    @classmethod
    def buildFromHeader( cls, header ):
        assert isinstance(header, TaskResourceHeader)

        curTr = TaskResource( header.relativePath, header.absolutePath )

        filesData = []
        for f in header.filesData:
            fname = os.path.join( header.absolutePath, f[ 0 ] ) 
            fdata = cls.readFile( fname )
            
            if fdata is None:
                return None

            filesData.append( ( f[ 0 ], f[ 1 ], fdata ) )

        curTr.filesData = filesData

        subDirResources = []
        for sdh in header.subDirHeaders:
            subDirRes = cls.buildFromHeader( sdh )

            if subDirRes is None:
                return None
            
            subDirResources.append( subDirRes )

        curTr.subDirResources = subDirResources

        return curTr        

    ####################
    # Dodaje tylko te pola, ktorych nie ma w headerze (i/lub nie zgadzaj? si? hasze)
    @classmethod
    def buildDeltaFromHeader( cls, header ):
        assert isinstance(header, TaskResourceHeader)

        #TODO: implement
        #TODO: serializacje calej klaski warto zrobic tym: http://code.activestate.com/recipes/189972-zip-and-pickle/ (tylko cPickle, a nie pickle)
        pass

    ####################
    def __init__( self, relativePath, absolutePath ):
        self.filesData          = []
        self.subDirResources    = []
        self.relativePath       = relativePath
        self.absolutePath       = absolutePath

    ####################
    def toString( self ):
        out = "\nROOT '{}' \n".format( self.absolutePath )

        if len( self.subDirResources ) > 0:
            out += "DIRS \n"
            for d in self.subDirResources:
                out += "    {}\n".format( d.relativePath )

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

if __name__ == "__main__":

    def walk_test( root ):
        for root, dirs, files in os.walk(root, topdown=True):
            for name in dirs:
                #print("D", os.path.join(root, name))
                print("D", root, name)
            #for name in files:
            #    print("F", os.path.join(root, name))
    
    def main():
        t = TaskResourceHeader( "test" )
        print t
        t = 0

    th = TaskResourceHeader.build( "test" )
    print th
    
    print "Entering task testing zone"
    v, m = TaskResource.validateHeader( th )

    if not v:
        print m
    else:
        tr = TaskResource.buildFromHeader( th )
        print tr

    #walk_test( "." )
    #main()
