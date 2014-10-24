import os
from golem.environments.Environment import Environment

class ThreeDSMaxEnvironment( Environment ):
    @classmethod
    def getId( cls ):
        return "3DSMAX"

    def __init__( self ):
        self.softwareEnvVar = ['ADSK_3DSMAX_x64_2015', 'ADSK_3DSMAX_x32_2015']
        self.softwareName = '3dsmaxcmd.exe'

    def checkSoftware( self ):
        for var in self.softwareEnvVar:
            if os.environ.get( var ):
                if os.path.isfile( os.path.join( os.environ.get( var ), '3dsmaxcmd.exe') ):
                    return True
        return False

    def supported( self ) :
        return self.checkSoftware()


