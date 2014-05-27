
import sys

sys.path.append('../src/')
sys.path.append('../src/core')
sys.path.append('../src/vm')
sys.path.append('../src/task')
sys.path.append('../src/task/resource')
sys.path.append('../testtasks/minilight/src')
sys.path.append('../testtasks/pbrt')
sys.path.append('../tools/')
sys.path.append('./../examples/gnr/ui')

from UiGen import genUiFiles
genUiFiles( "./../examples/gnr/ui" )

from Application import GNRGui
from GNRApplicationLogic import GNRApplicationLogic

from TaskStatus import TaskStatus, RendereInfo, TestTaskInfo, RendererDefaults

def buidPBRTRendererInfo():
    defaults = RendererDefaults()
    defaults.fullTaskTimeout    = 4 * 3600
    defaults.minSubtaskTime     = 60
    defaults.subtaskTimeout     = 20 * 60
    defaults.samplesPerPixel    = 200
    defaults.outputFormat       = "EXR"
    defaults.mainProgramFile    = "./../testtasks/pbrt/pbrt_compact.py"
    

    renderer = RendereInfo( "PBRT", defaults )
    renderer.filters = ["box", "gaussian", "mitchell", "sinc", "triange" ]
    renderer.pathTracers = ["aggregatetest", "createprobes", "metropolis", "sampler", "surfacepoints"]
    renderer.outputFormats = [ "PFM", "TGA", "EXR" ]
    
    return renderer


def main():

    logic   = GNRApplicationLogic()
    app     = GNRGui( logic )

    logic.registerGui( app.getMainWindow() )

    logic.registerNewRendererType( buidPBRTRendererInfo() )

    logic.registerNewTestTaskType( TestTaskInfo( "CornellBox" ) )

    #####
    tasks = []
    ts1 = TaskStatus()
    ts2 = TaskStatus()
    ts1.id = "321"
    ts1.maxSubtask = 20000
    ts1.minSubtask = 2000
    ts1.progress = 0.34
    ts1.status = "Computing"
    ts2.id = "123"
    ts2.progress = 0.97
    ts2.status = "Computing"
    tasks.append( ts1 )
    tasks.append( ts2 )

    logic.addTasks( tasks )

    app.execute()

main()