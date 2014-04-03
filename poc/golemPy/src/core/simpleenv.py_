import os

DATA_DIRECTORY  = "node_data"

class SimpleEnv:

    @classmethod
    def __envDirGuard( cls ):
        if not os.path.exists( DATA_DIRECTORY ):
            os.makedirs( DATA_DIRECTORY )

    @classmethod
    def envFileName( cls, filename ):
        cls.__envDirGuard()

        if DATA_DIRECTORY in filename:
            return filename

        return os.path.join( DATA_DIRECTORY, filename )

    @classmethod
    def openEnvFile( cls, filename, options = 'a' ):
        fname = cls.envFileName( filename )

        if not os.path.exists( filename ):
            with open( fname, 'a' ):
                os.utime( fname, None )

        return open( fname, options )
