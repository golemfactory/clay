from examples.gnr.task.PbrtGNRTask import PbrtTaskBuilder
from examples.gnr.task.VRayTask import VRayTaskBuilder
from examples.gnr.task.ThreeDSMaxTask import ThreeDSMaxTaskBuilder
from examples.gnr.task.PythonGNRTask import PythonGNRTaskBuilder

def buildPBRTTaskType():
    return TaskType( "PBRT", PbrtTaskBuilder )

def build3dsMaxTaskType():
    return TaskType( "3ds Max Renderer", ThreeDSMaxTaskBuilder)

def buildVRayTaskType():
    return TaskType( "VRay Standalone", VRayTaskBuilder)

def buildPythonGNRTaskType():
    return TaskType( "Python GNR Task", PythonGNRTaskBuilder )

class TaskType:
    def __init__( self, name, taskBuilderType ):
        self.name = name
        self.taskBuilderType = taskBuilderType