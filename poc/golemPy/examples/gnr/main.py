import sys
import os
import logging
import logging.config

sys.path.append( os.environ.get( 'GOLEM' ) )

from tools.UiGen import genUiFiles
genUiFiles( "ui" )

from GNRApplicationLogic import GNRApplicationLogic

from Application import GNRGui
#from InfoServer import InfoServer

from TaskState import RendererDefaults, RendererInfo, TestTaskInfo
from task.PbrtGNRTask import PbrtTaskBuilder, PbrtRendererOptions
from task.MR3dsMaxTask import MentalRayTaskBuilder, MentalRayRendererOptions
from examples.gnr.ui.PbrtDialog import PbrtDialog
from examples.gnr.ui.MentalRayDialog import MentalRayDialog
from examples.gnr.customizers.PbrtDialogCustomizer import PbrtDialogCustomizer
from examples.gnr.customizers.MentalRayDialogCustomizer import MentalRayDialogCustomizer
from examples.gnr.RenderingEnvironment import ThreeDSMaxEnvironment, PBRTEnvironment, Environment

from golem.Client import startClient

from examples.manager.GNRManagerLogic import runAdditionalNodes, runManager

def buildPBRTRendererInfo():
    defaults = RendererDefaults()
    defaults.outputFormat       = "EXR"
    defaults.mainProgramFile    = "d:/test_run/pbrt_compact.py"
    

    renderer                = RendererInfo( "PBRT", defaults, PbrtTaskBuilder, PbrtDialog, PbrtDialogCustomizer, PbrtRendererOptions )
    renderer.filters        = [ "box", "gaussian", "mitchell", "sinc", "triangle" ]
    renderer.pathTracers    = [ "adaptive", "bestcandidate", "halton", "lowdiscrepancy", "random", "stratified" ]
    renderer.outputFormats  = [ "BMP", "EPS", "EXR", "GIF", "IM", "JPEG", "PCX", "PDF", "PNG", "PPM", "TIFF" ]
    renderer.scenFileExt    = [ "pbrt" ]

    return renderer


def buildMentalRayRendererInfo():
    defaults = RendererDefaults()
    defaults.outputFormat       = "EXR"
    defaults.mainProgramFile    = "d:/test_run/pbrt_compact.py"


    renderer                = RendererInfo( "MentalRay", defaults, MentalRayTaskBuilder, MentalRayDialog, MentalRayDialogCustomizer, MentalRayRendererOptions )
    renderer.filters        = ["box", "gaussian", "mitchell", "sinc", "triangle" ]
    renderer.pathTracers    = ["adaptive", "bestcandidate", "halton", "lowdiscrepancy", "random", "stratified"]
    renderer.outputFormats  = [ "BMP", "EPS", "EXR", "GIF", "IM", "JPEG", "PCD", "PCX", "PNG", "PPM", "PSD", "TIFF", "XBM", "XPM" ]
    renderer.sceneFileExt   = [ "max",  "zip" ]

    return renderer

def main():

    logging.config.fileConfig('logging.ini', disable_existing_loggers=False)

    logic   = GNRApplicationLogic()
    app     = GNRGui( logic )

    # task = TaskState()
    # computer = ComputerState()
    # computer.subtaskState.subtaskDefinition = "sdasuncbnasocbno \n duiasidun uia\n diausndianu \n"
    # computer.subtaskState.subtaskId = "5675128936189263"
    # computer.subtaskState.subtaskProgress = 0.43
    # computer.subtaskState.subtaskRemTime = 3200
    # computer.subtaskState.subtaskStatus = TaskStatus.computing
    # computer.ipAddress = "123.53.23.11"
    # computer.performance = 20000
    # computer.nodeId = "jsajcnas89090casdc"
    #
    # task.computers[ computer.nodeId ] = computer
    #
    # task.definition.id = "asiomxcasoncd90jscsnpac"

    try:
        import qt4reactor
    except ImportError:
        # Maybe qt4reactor is placed inside twisted.internet in site-packages?
        from twisted.internet import qt4reactor
    qt4reactor.install()
    from twisted.internet import reactor

    logic.registerGui( app.getMainWindow() )

    #app.appLogic.addTasks( [ task ] )

    logic.registerNewRendererType( buildPBRTRendererInfo() )
    logic.registerNewRendererType( buildMentalRayRendererInfo() )
    logic.registerNewTestTaskType( TestTaskInfo( "CornellBox" ) )

    path = os.getcwd()
    def runGNRNodes( numNodes ):
        runAdditionalNodes( path, numNodes )

    nmPath = os.path.join(path, "..\\manager\\" )
    def runGNRManager( ):
        runManager( nmPath )

    logic.registerStartNewNodeFunction( runGNRNodes )
    logic.registerStartNodesManagerFunction( runGNRManager )

    environments = [PBRTEnvironment(), ThreeDSMaxEnvironment(), Environment() ]

    client = startClient( )

    for env in environments:
        client.environmentsManager.addEnvironment( env )
    logic.registerClient( client )
    logic.checkNetworkState()
    #logic.startNodesManagerClient()
#    infoServer = InfoServer( client, 55555, 55556, 59999 )
#    infoServer.start()

    app.execute( False )

    reactor.run()

main()
