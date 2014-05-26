
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

from TaskStatus import TaskStatus

def main():

    logic   = GNRApplicationLogic()
    app     = GNRGui( logic )

    logic.registerGui( app.getMainWindow() )



    #####
    tasks = []
    ts1 = TaskStatus()
    ts2 = TaskStatus()
    ts1.id = "321"
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