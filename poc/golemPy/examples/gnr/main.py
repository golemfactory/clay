import sys

sys.path.append('./../../')

from GNRApplicationLogic import GNRApplicationLogic

from tools.UiGen import genUiFiles
genUiFiles( "ui" )

from Application import GNRGui

from TaskState import RendererDefaults, RendererInfo, TestTaskInfo
from task.PbrtGNRTask import PbrtTaskBuilder

from golem.Client import startClient

def buidPBRTRendererInfo():
    defaults = RendererDefaults()
    defaults.fullTaskTimeout    = 4 * 3600
    defaults.minSubtaskTime     = 60
    defaults.subtaskTimeout     = 20 * 60
    defaults.samplesPerPixel    = 200
    defaults.outputFormat       = "EXR"
    defaults.mainProgramFile    = "d:/test_run/pbrt_compact.py"
    

    renderer                = RendererInfo( "PBRT", defaults, PbrtTaskBuilder )
    renderer.filters        = ["box", "gaussian", "mitchell", "sinc", "triange" ]
    renderer.pathTracers    = ["aggregatetest", "createprobes", "metropolis", "sampler", "surfacepoints"]
    renderer.outputFormats  = [ "BMP", "DCX", "EPS", "GIF", "IM", "IM", "JPEG", "PCD", "PCX", "PDF", "PNG", "PPM", "PSD", "TIFF", "XBM", "XPM" ]

    return renderer


def main():

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

    logic.registerNewRendererType( buidPBRTRendererInfo() )

    logic.registerNewTestTaskType( TestTaskInfo( "CornellBox" ) )


    client = startClient( )

    logic.registerClient( client )


    app.execute( False )

    reactor.run()

main()