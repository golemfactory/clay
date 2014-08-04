import sys

sys.path.append('./../../')

from tools.UiGen import genUiFiles
genUiFiles( "ui" )

from GNRApplicationLogic import GNRApplicationLogic

from Application import GNRGui

from TaskState import TaskState, RendererInfo, TestTaskInfo, RendererDefaults, ComputerState, TaskStatus
from TestEngine import TestEngine
from task.PbrtGNRTask import PbrtTaskBuilder

def buidPBRTRendererInfo():
    defaults = RendererDefaults()
    defaults.fullTaskTimeout    = 4 * 3600
    defaults.minSubtaskTime     = 60
    defaults.subtaskTimeout     = 20 * 60
    defaults.samplesPerPixel    = 200
    defaults.outputFormat       = "EXR"
    defaults.mainProgramFile    = "./../../testtasks/pbrt/pbrt_compact.py"
    

    renderer                = RendererInfo( "PBRT", defaults, PbrtTaskBuilder )
    renderer.filters        = ["box", "gaussian", "mitchell", "sinc", "triange" ]
    renderer.pathTracers    = ["aggregatetest", "createprobes", "metropolis", "sampler", "surfacepoints"]
    renderer.outputFormats  = [ "PFM", "TGA", "EXR" ]

    return renderer


def main():

    logic   = GNRApplicationLogic()
    app     = GNRGui( logic )

    task = TaskState()
    computer = ComputerState()
    computer.subtaskState.subtaskDefinition = "sdasuncbnasocbno \n duiasidun uia\n diausndianu \n"
    computer.subtaskState.subtaskId = "5675128936189263"
    computer.subtaskState.subtaskProgress = 0.43
    computer.subtaskState.subtaskRemTime = 3200
    computer.subtaskState.subtaskStatus = TaskStatus.computing
    computer.ipAddress = "123.53.23.11"
    computer.performance = 20000
    computer.nodeId = "jsajcnas89090casdc"

    task.computers[ computer.nodeId ] = computer

    task.definition.id = "asiomxcasoncd90jscsnpac"

    logic.registerGui( app.getMainWindow() )

    app.appLogic.addTasks( [ task ] )

    logic.registerNewRendererType( buidPBRTRendererInfo() )

    logic.registerNewTestTaskType( TestTaskInfo( "CornellBox" ) )

    te = TestEngine( logic )

    app.execute()

main()