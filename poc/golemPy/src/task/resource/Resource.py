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
    #walk_test( "." )
    #main()
