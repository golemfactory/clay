
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

from TaskState import TaskState, RendereInfo, TestTaskInfo, RendererDefaults

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

    app.execute()

main()