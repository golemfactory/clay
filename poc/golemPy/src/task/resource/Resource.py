import sys
sys.path.append('../../core/')

from simplehash import SimpleHash

import os
from os.path import join, isdir, isfile

class TaskResourceHeader:

    ####################
    @classmethod
    def build( cls, relativeRoot, absoluteRoot ):
        curTh = TaskResourceHeader( relativeRoot, absoluteRoot )

        dirs  = [ ( name, os.path.join( absoluteRoot, name ) ) for name in os.listdir( absoluteRoot ) if os.path.isdir( os.path.join( absoluteRoot, name ) ) ]
        files = [ name for name in os.listdir( absoluteRoot ) if os.path.isfile( os.path.join( absoluteRoot, name ) ) ]

        for f in files:

        print dirs
        print files

        return None

    ####################
    def __init__( self, relativePath, absolutePath ):
        self.dirs   = []
        self.files  = []
        self.relativePath = relativePath
        self.absolutePath = absolutePath

    ####################
    def __buildResourceHeader( self, path ):

        dirs = [ name for name in os.listdir( path ) if os.path.isdir( os.path.join( path, name ) ) ]

        for d in dirs:
            self.dirs.append( [ d, TaskResourceHeader( os.path.join( path, d ) ) ] )
         
         
        files = [ name for name in os.listdir( path ) if os.path.isfile( os.path.join( path, name ) ) ]  
             
        for f in files:
            fh = open( os.path.join( path, f ), "r" )
            self.files.append( [ f, SimpleHash.hash_base64( fh.read() ) ] )

    ####################
    def toString( self ):
        out = "\nROOT {} \n".format( self.path )
        out += "DIRS \n"
        for d in self.dirs:
            out += "{}\n".format( d[ 0 ] )

        out += "FILES \n"
        for f in self.files:
            out += "{} \n".format( f )

        for d in self.dirs:
            out += d[ 1 ].toString()

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

    th = TaskResourceHeader.build( "test", "test" )
    #walk_test( "." )
    #main()
