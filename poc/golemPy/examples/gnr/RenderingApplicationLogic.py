import logging
import os

from examples.gnr.GNRApplicationLogic import GNRApplicationLogic
from examples.gnr.RenderingTaskState import RenderingTaskState
from examples.gnr.customizers.RenderingMainWindowCustomizer import RenderingMainWindowCustomizer

logger = logging.getLogger(__name__)

class RenderingApplicationLogic( GNRApplicationLogic ):
    ######################
    def __init__( self ):
        GNRApplicationLogic.__init__( self )
        self.renderers          = {}
        self.currentRenderer    = None
        self.defaultRenderer    = None

    ######################
    def getRenderers( self ):
        return self.renderers

    ######################
    def getRenderer( self, name ):
        if name in self.renderers:
            return self.renderers[ name ]
        else:
            assert False, "Renderer {} not registered".format( name )

    ######################
    def getDefaultRenderer( self ):
        return self.defaultRenderer

    ######################
    def registerNewRendererType( self, renderer ):
        if renderer.name not in self.renderers:
            self.renderers[ renderer.name ] = renderer
            if len( self.renderers ) == 1:
                self.defaultRenderer = renderer
        else:
            assert False, "Renderer {} already registered".format( renderer.name )

    ######################
    def setCurrentRenderer( self, rname ):
        if rname in self.renderers:
            self.currentRenderer = self.renderers[ rname ]
        else:
            assert False, "Unreachable"

    ######################
    def getCurrentRenderer( self ):
        return self.currentRenderer

    ######################
    def _getNewTaskState( self ):
        return RenderingTaskState()

    ######################
    def _getBuilder( self, taskState ):
        return self.renderers[ taskState.definition.renderer ].taskBuilderType( self.client.getId(), taskState.definition, self.client.getRootPath( ) )

    ######################
    def _validateTaskState( self, taskState ):

        td = taskState.definition
        if td.renderer in self.renderers:
            r = self.renderers[ td.renderer ]

            if not os.path.exists( td.mainProgramFile ):
                self._showErrorWindow( "Main program file does not exist: {}".format( td.mainProgramFile ) )
                return False

            if not self.__checkOutputFile(td.outputFile):
                return False

            if not os.path.exists( td.mainSceneFile ):
                self._showErrorWindow( "Main scene file is not properly set" )
                return False


        else:
            return False

        return True


    ######################
    def __checkOutputFile(self, outputFile):
        try:
            if os.path.exists( outputFile ):
                f = open( outputFile , 'a')
                f.close()
            else:
                f = open( outputFile , 'w')
                f.close()
                os.remove(outputFile)
            return True
        except IOError:
            self.__showErrorWindow( "Cannot open file: {}".format( outputFile ))
            return False
        except:
            self.__showErrorWindow( "Output file is not properly set" )
            return False