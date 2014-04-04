import sys
sys.path.append('../../core/')

from simplehash import SimpleHash

import os
from os.path import join, isdir, isfile

class TaskResourceHeader:
    ####################
    def __init__( self, path ):
        self.dirs   = []
        self.files  = []
        self.path = path
        self.__buildResourceHeader( path )

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

def main():
    t = TaskResourceHeader( "test" )
    print t
    t = 0


main()
