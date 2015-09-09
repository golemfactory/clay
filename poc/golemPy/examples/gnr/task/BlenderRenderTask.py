import logging
import random
import os
import math

from collections import OrderedDict
from PIL import Image, ImageChops

from golem.task.TaskState import SubtaskStatus

from examples.gnr.RenderingDirManager import getTestTaskPath, getTmpPath
from examples.gnr.RenderingEnvironment import BlenderEnvironment
from examples.gnr.RenderingTaskState import RendererDefaults, RendererInfo

from examples.gnr.task.GNRTask import GNROptions, checkSubtask_idWrapper
from examples.gnr.task.FrameRenderingTask import FrameRenderingTask, FrameRenderingTaskBuiler, get_taskBoarder, get_taskNumFromPixels
from examples.gnr.task.RenderingTaskCollector import RenderingTaskCollector, exr_to_pil
from examples.gnr.task.SceneFileEditor import regenerateBlenderCropFile

from examples.gnr.ui.BlenderRenderDialog import BlenderRenderDialog
from examples.gnr.customizers.BlenderRenderDialogCustomizer import BlenderRenderDialogCustomizer

logger = logging.getLogger(__name__)

##############################################
def buildBlenderRendererInfo():
    defaults = RendererDefaults()
    defaults.outputFormat = "EXR"
    defaults.mainProgramFile = os.path.normpath(os.path.join(os.environ.get('GOLEM'), 'examples/tasks/blenderTask.py'))
    defaults.minSubtasks = 1
    defaults.maxSubtasks = 100
    defaults.defaultSubtasks = 6

    renderer = RendererInfo("Blender", defaults, BlenderRenderTaskBuilder, BlenderRenderDialog, BlenderRenderDialogCustomizer, BlenderRendererOptions)
    renderer.outputFormats = [ "PNG", "TGA", "EXR" ]
    renderer.scene_fileExt = [ "blend" ]
    renderer.get_taskNumFromPixels = get_taskNumFromPixels
    renderer.get_taskBoarder = get_taskBoarder

    return renderer

##############################################
class BlenderRendererOptions(GNROptions):
    #######################
    def __init__(self):
        self.environment = BlenderEnvironment()
        self.engineValues = ["BLENDER_RENDER", "BLENDER_GAME", "CYCLES"]
        self.engine = "BLENDER_RENDER"
        self.useFrames = False
        self.frames = range(1, 11)

##############################################
class BlenderRenderTaskBuilder(FrameRenderingTaskBuiler):
    #######################
    def build(self):
        mainSceneDir = os.path.dirname(self.taskDefinition.mainSceneFile)

        vRayTask = BlenderRenderTask(      self.client_id,
                                   self.taskDefinition.task_id,
                                   mainSceneDir,
                                   self.taskDefinition.mainSceneFile,
                                   self.taskDefinition.mainProgramFile,
                                   self._calculateTotal(buildBlenderRendererInfo(), self.taskDefinition),
                                   self.taskDefinition.resolution[0],
                                   self.taskDefinition.resolution[1],
                                   os.path.splitext(os.path.basename(self.taskDefinition.output_file))[0],
                                   self.taskDefinition.output_file,
                                   self.taskDefinition.outputFormat,
                                   self.taskDefinition.full_task_timeout,
                                   self.taskDefinition.subtask_timeout,
                                   self.taskDefinition.resources,
                                   self.taskDefinition.estimated_memory,
                                   self.root_path,
                                   self.taskDefinition.rendererOptions.useFrames,
                                   self.taskDefinition.rendererOptions.frames,
                                   self.taskDefinition.rendererOptions.engine
                                  )
        return self._setVerificationOptions(vRayTask)

    def _setVerificationOptions(self, newTask):
        newTask = FrameRenderingTaskBuiler._setVerificationOptions(self, newTask)
        if newTask.advanceVerification:
            boxX = max(newTask.verificationOptions.boxSize[0], 8)
            boxY = max(newTask.verificationOptions.boxSize[1], 8)
            newTask.boxSize = (boxX, boxY)
        return newTask


##############################################
class BlenderRenderTask(FrameRenderingTask):
    #######################
    def __init__(self,
                  client_id,
                  task_id,
                  mainSceneDir,
                  mainSceneFile,
                  mainProgramFile,
                  total_tasks,
                  resX,
                  resY,
                  outfilebasename,
                  output_file,
                  outputFormat,
                  full_task_timeout,
                  subtask_timeout,
                  taskResources,
                  estimated_memory,
                  root_path,
                  useFrames,
                  frames,
                  engine,
                  return_address = "",
                  return_port = 0,
                  key_id = ""):

        FrameRenderingTask.__init__(self, client_id, task_id, return_address, return_port, key_id,
                          BlenderEnvironment.get_id(), full_task_timeout, subtask_timeout,
                          mainProgramFile, taskResources, mainSceneDir, mainSceneFile,
                          total_tasks, resX, resY, outfilebasename, output_file, outputFormat,
                          root_path, estimated_memory, useFrames, frames)

        cropTask = os.path.normpath(os.path.join(os.environ.get('GOLEM'), 'examples\\tasks\\blenderCrop.py'))
        try:
            with open(cropTask) as f:
                self.scriptSrc = f.read()
        except Exception, err:
            logger.error("Wrong script file: {}".format(str(err)))
            self.scriptSrc = ""

        self.engine = engine

        self.framesGiven = {}
        for frame in frames:
            self.framesGiven[ frame ] = {}

    #######################
    def query_extra_data(self, perf_index, num_cores = 0, client_id = None):

        if not self._acceptClient(client_id):
            logger.warning(" Client {} banned from this task ".format(client_id))
            return None

        start_task, end_task = self._getNextTask()

        working_directory = self._getWorkingDirectory()
        scene_file = self._getSceneFileRelPath()

        if self.useFrames:
            frames, parts = self._chooseFrames(self.frames, start_task, self.total_tasks)
        else:
            frames = [1]
            parts = 1

        if not self.useFrames:
            minY = (self.total_tasks - start_task) * (1.0 / float(self.total_tasks))
            maxY = (self.total_tasks - start_task + 1) * (1.0 / float(self.total_tasks))
        elif parts > 1:
            minY = (parts - self._countPart(start_task, parts)) * (1.0 / float(parts))
            maxY = (parts - self._countPart(start_task, parts) + 1) * (1.0 / float(parts))
        else:
            minY = 0.0
            maxY = 1.0

        scriptSrc = regenerateBlenderCropFile(self.scriptSrc, self.resX, self.resY, 0.0, 1.0, minY, maxY)
        extra_data =          {      "path_root": self.mainSceneDir,
                                    "start_task" : start_task,
                                    "end_task": end_task,
                                    "total_tasks": self.total_tasks,
                                    "outfilebasename" : self.outfilebasename,
                                    "scene_file" : scene_file,
                                    "scriptSrc": scriptSrc,
                                    "engine": self.engine,
                                    "frames": frames,
                                }


        hash = "{}".format(random.getrandbits(128))
        self.subTasksGiven[ hash ] = extra_data
        self.subTasksGiven[ hash ][ 'status' ] = SubtaskStatus.starting
        self.subTasksGiven[ hash ][ 'perf' ] = perf_index
        self.subTasksGiven[ hash ][ 'client_id' ] = client_id
        self.subTasksGiven[ hash ][ 'parts' ] = parts


        if not self.useFrames:
            self._updateTaskPreview()
        else:
            self._updateFrameTaskPreview()

        return self._newComputeTaskDef(hash, extra_data, working_directory, perf_index)

    #######################
    def query_extra_dataForTestTask(self):

        working_directory = self._getWorkingDirectory()
        scene_file = self._getSceneFileRelPath()

        if self.useFrames:
            frames = [ self.frames[0] ]
        else:
            frames = []

        if self.useFrames:
            frames = [ self.frames[0] ]
        else:
            frames = [1]

        scriptSrc = regenerateBlenderCropFile(self.scriptSrc, 8, 8, 0.0, 1.0, 0.0, 1.0)

        extra_data =          {      "path_root": self.mainSceneDir,
                                    "start_task" : 1,
                                    "end_task": 1,
                                    "total_tasks": self.total_tasks,
                                    "outfilebasename" : self.outfilebasename,
                                    "scene_file" : scene_file,
                                    "scriptSrc": scriptSrc,
                                    "engine": self.engine,
                                    "frames": frames
                                }

        hash = "{}".format(random.getrandbits(128))

        self.test_taskResPath = getTestTaskPath(self.root_path)
        logger.debug(self.test_taskResPath)
        if not os.path.exists(self.test_taskResPath):
            os.makedirs(self.test_taskResPath)

        return self._newComputeTaskDef(hash, extra_data, working_directory, 0)

    #######################
    def _getPartSize(self) :
        if not self.useFrames:
            resY = int (math.floor(float(self.resY) / float(self.total_tasks)))
        elif len(self.frames) >= self.total_tasks:
            resY = self.resY
        else:
            parts = self.total_tasks / len(self.frames)
            resY = int (math.floor(float(self.resY) / float(parts)))
        return self.resX, resY

    #######################
    @checkSubtask_idWrapper
    def _getPartImgSize(self, subtask_id, advTestFile) :
        x, y = self._getPartSize()
        return 0, 0, x, y

    #######################
    @checkSubtask_idWrapper
    def _changeScope(self, subtask_id, startBox, trFile):
        extra_data, _ = FrameRenderingTask._changeScope(self, subtask_id, startBox, trFile)
        minX = startBox[0]/float(self.resX)
        maxX = (startBox[0] + self.verificationOptions.boxSize[0] + 1) / float(self.resX)
        startY = startBox[1]+ (extra_data['start_task'] - 1) * (self.resY / float(extra_data['total_tasks']))
        maxY = float(self.resY - startY) /self.resY
        minY = max(float(self.resY - startY - self.verificationOptions.boxSize[1] - 1) /self.resY, 0.0)
        scriptSrc = regenerateBlenderCropFile(self.scriptSrc, self.resX, self.resY, minX, maxX, minY, maxY)
        extra_data['scriptSrc'] = scriptSrc
        return extra_data, (0, 0)

    def __getFrameNumFromOutputFile(self, file_):
        file_name = os.path.basename(file_)
        file_name, ext = os.path.splitext(file_name)
        idx = file_name.find(self.outfilebasename)
        return int(file_name[ idx + len(self.outfilebasename):])

    #######################
    def _updatePreview(self, newChunkFilePath, chunkNum):

        if newChunkFilePath.endswith(".exr"):
            img = exr_to_pil(newChunkFilePath)
        else:
            img = Image.open(newChunkFilePath)

        imgOffset = Image.new("RGB", (self.resX, self.resY))
        try:
            offset = int (math.floor((chunkNum - 1) * float(self.resY) / float(self.total_tasks)))
            imgOffset.paste(img, (0, offset))
        except Exception, err:
            logger.error("Can't generate preview {}".format(str(err)))

        tmp_dir = getTmpPath(self.header.client_id, self.header.task_id, self.root_path)

        self.previewFilePath = "{}".format(os.path.join(tmp_dir, "current_preview"))

        if os.path.exists(self.previewFilePath):
            imgCurrent = Image.open(self.previewFilePath)
            imgCurrent = ImageChops.add(imgCurrent, imgOffset)
            imgCurrent.save(self.previewFilePath, "BMP")
        else:
            imgOffset.save(self.previewFilePath, "BMP")

    #######################
    def _getOutputName(self, frameNum, numStart):
        num = str(frameNum)
        return "{}{}.{}".format(self.outfilebasename, num.zfill(4), self.outputFormat)