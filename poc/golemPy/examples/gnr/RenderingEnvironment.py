import os
from golem.environments.Environment import Environment

class ThreeDSMaxEnvironment( Environment ):
    @classmethod
    def getId( cls ):
        return "3DSMAX"

    def __init__( self ):
        Environment.__init__( self )
        self.software.append('3DS Max Studio 2015')
        self.software.append('Windows')
        self.softwareEnvVar = ['ADSK_3DSMAX_x64_2015', 'ADSK_3DSMAX_x32_2015']
        self.softwareName = '3dsmaxcmd.exe'
        self.shortDescription = "3DS MAX Studio command tool (http://www.autodesk.pl/products/3ds-max/overview)"

    def checkSoftware( self ):
        for var in self.softwareEnvVar:
            if os.environ.get( var ):
                if os.path.isfile( os.path.join( os.environ.get( var ), '3dsmaxcmd.exe') ):
                    return True
        return False

    def supported( self ) :
        return self.checkSoftware()

class PBRTEnvironment ( Environment ):
    @classmethod
    def getId( cls ):
        return "PBRT"

    def __init__( self ):
        Environment.__init__( self )
        self.software.append('Windows')
        self.shortDescription =  "PBRT renderer (http://www.pbrt.org/)  "

    def supported( self ) :
        return True
