from examples.gnr.task.PbrtGNRTask import PbrtGNRTaskBuilder, buildPBRTRendererInfo, PbrtRendererOptions
from examples.gnr.task.VRayTask import VRayTaskBuilder
from examples.gnr.task.ThreeDSMaxTask import ThreeDSMaxTaskBuilder
from examples.gnr.task.PythonGNRTask import PythonGNRTaskBuilder
from examples.gnr.task.LuxRenderTask import LuxRenderTaskBuilder
from examples.gnr.task.BlenderRenderTask import BlenderRenderTaskBuilder
from examples.gnr.task.GNRTask import GNROptions

from examples.gnr.ui.PbrtTaskDialog import PbrtTaskDialog
from examples.gnr.customizers.PbrtTaskDialogCustomizer import PbrtTaskDialogCustomizer

def buildPBRTTaskType():
    renderer = buildPBRTRendererInfo()
    options = GNROptions()
    options.outputFormats = renderer.outputFormats
    options.scene_fileExt = renderer.scene_fileExt
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
    options.full_task_timeout = renderer.defaults.full_task_timeout
    options.min_subtask_time = renderer.defaults.min_subtask_time
    options.minSubtasks = renderer.defaults.minSubtasks
    options.maxSubtasks = renderer.defaults.maxSubtasks
    options.defaultSubtasks = renderer.defaults.defaultSubtasks
    options.mainSceneFile = ''
    options.output_file = ''
    options.verificationOptions = None

    return TaskType("PBRT", PbrtGNRTaskBuilder, options, PbrtTaskDialog, PbrtTaskDialogCustomizer)

def build3dsMaxTaskType():
    return TaskType("3ds Max Renderer", ThreeDSMaxTaskBuilder)

def buildVRayTaskType():
    return TaskType("VRay Standalone", VRayTaskBuilder)

def buildLuxRenderTaskType():
    return TaskType("LuxRender", LuxRenderTaskBuilder)

def buildBlenderRenderTaskType():
    return TaskType("BlenderRender", BlenderRenderTaskBuilder)

def buildPythonGNRTaskType():
    return TaskType("Python GNR Task", PythonGNRTaskBuilder)

class TaskType:
    def __init__(self, name, task_builderType, options = None, dialog = None, dialogCustomizer = None):
        self.name = name
        self.task_builderType = task_builderType
        self.options = options
        self.dialog = dialog
        self.dialogCustomizer = dialogCustomizer