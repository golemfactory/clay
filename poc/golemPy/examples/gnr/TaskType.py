from examples.gnr.task.PbrtGNRTask import PbrtGNRTaskBuilder, buildPBRTRendererInfo, PbrtRendererOptions
from examples.gnr.task.VRayTask import VRayTaskBuilder
from examples.gnr.task.ThreeDSMaxTask import ThreeDSMaxTaskBuilder
from examples.gnr.task.PythonGNRTask import PythonGNRTaskBuilder
from examples.gnr.task.GNRTask import GNROptions

from examples.gnr.ui.PbrtTaskDialog import PbrtTaskDialog
from examples.gnr.customizers.PbrtTaskDialogCustomizer import PbrtTaskDialogCustomizer

def buildPBRTTaskType():
    renderer = buildPBRTRendererInfo()
    options = GNROptions()
    options.outputFormats = renderer.outputFormats
    options.sceneFileExt = renderer.sceneFileExt
    options.defaults = renderer.defaults
    rendererOptions = PbrtRendererOptions()
    options.filters = rendererOptions.filters
    options.pixelFilter = rendererOptions.pixelFilter
    options.pathTracers = rendererOptions.pathTracers
    options.algorithmType = rendererOptions.algorithmType
    options.samplesPerPixelCount = rendererOptions.samplesPerPixelCount
    options.resolution = renderer.defaults.resolution
    options.outputFormat = renderer.defaults.outputFormat
    options.mainProgramFile = renderer.defaults.mainProgramFile
    options.fullTaskTimeout = renderer.defaults.fullTaskTimeout
    options.minSubtaskTime = renderer.defaults.minSubtaskTime
    options.minSubtasks = renderer.defaults.minSubtasks
    options.maxSubtasks = renderer.defaults.maxSubtasks
    options.defaultSubtasks = renderer.defaults.defaultSubtasks
    options.mainSceneFile = ''
    options.outputFile = ''
    options.verificationOptions = None

    return TaskType( "PBRT", PbrtGNRTaskBuilder, options, PbrtTaskDialog, PbrtTaskDialogCustomizer)

def build3dsMaxTaskType():
    return TaskType( "3ds Max Renderer", ThreeDSMaxTaskBuilder)

def buildVRayTaskType():
    return TaskType( "VRay Standalone", VRayTaskBuilder)

def buildPythonGNRTaskType():
    return TaskType( "Python GNR Task", PythonGNRTaskBuilder )

class TaskType:
    def __init__( self, name, taskBuilderType, options = None, dialog = None, dialogCustomizer = None ):
        self.name = name
        self.taskBuilderType = taskBuilderType
        self.options = options
        self.dialog = dialog
        self.dialogCustomizer = dialogCustomizer