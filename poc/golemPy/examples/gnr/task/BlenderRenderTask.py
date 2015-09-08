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
    renderer.sceneFileExt = [ "blend" ]
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
                                   self.taskDefinition.fullTaskTimeout,
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
                  totalTasks,
                  resX,
                  resY,
                  outfilebasename,
                  output_file,
                  outputFormat,
                  fullTaskTimeout,
                  subtask_timeout,
                  taskResources,
                  estimated_memory,
                  root_path,
                  useFrames,
                  frames,
                  engine,
                  returnAddress = "",
                  returnPort = 0,
                  key_id = ""):

        FrameRenderingTask.__init__(self, client_id, task_id, returnAddress, returnPort, key_id,
                          BlenderEnvironment.getId(), fullTaskTimeout, subtask_timeout,
                          mainProgramFile, taskResources, mainSceneDir, mainSceneFile,
                          totalTasks, resX, resY, outfilebasename, output_file, outputFormat,
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
    def queryExtraData(self, perfIndex, num_cores = 0, client_id = None):

        if not self._acceptClient(client_id):
            logger.warning(" Client {} banned from this task ".format(client_id))
            return None

        startTask, endTask = self._getNextTask()

        workingDirectory = self._getWorkingDirectory()
        sceneFile = self._getSceneFileRelPath()

        if self.useFrames:
            frames, parts = self._chooseFrames(self.frames, startTask, self.totalTasks)
        else:
            frames = [1]
            parts = 1

        if not self.useFrames:
            minY = (self.totalTasks - startTask) * (1.0 / float(self.totalTasks))
            maxY = (self.totalTasks - startTask + 1) * (1.0 / float(self.totalTasks))
        elif parts > 1:
            minY = (parts - self._countPart(startTask, parts)) * (1.0 / float(parts))
            maxY = (parts - self._countPart(startTask, parts) + 1) * (1.0 / float(parts))
        else:
            minY = 0.0
            maxY = 1.0

        scriptSrc = regenerateBlenderCropFile(self.scriptSrc, self.resX, self.resY, 0.0, 1.0, minY, maxY)
        extra_data =          {      "pathRoot": self.mainSceneDir,
                                    "startTask" : startTask,
                                    "endTask": endTask,
                                    "totalTasks": self.totalTasks,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFile" : sceneFile,
                                    "scriptSrc": scriptSrc,
                                    "engine": self.engine,
                                    "frames": frames,
                                }


        hash = "{}".format(random.getrandbits(128))
        self.subTasksGiven[ hash ] = extra_data
        self.subTasksGiven[ hash ][ 'status' ] = SubtaskStatus.starting
        self.subTasksGiven[ hash ][ 'perf' ] = perfIndex
        self.subTasksGiven[ hash ][ 'client_id' ] = client_id
        self.subTasksGiven[ hash ][ 'parts' ] = parts


        if not self.useFrames:
            self._updateTaskPreview()
        else:
            self._updateFrameTaskPreview()

        return self._newComputeTaskDef(hash, extra_data, workingDirectory, perfIndex)

    #######################
    def queryExtraDataForTestTask(self):

        workingDirectory = self._getWorkingDirectory()
        sceneFile = self._getSceneFileRelPath()

        if self.useFrames:
            frames = [ self.frames[0] ]
        else:
            frames = []

        if self.useFrames:
            frames = [ self.frames[0] ]
        else:
            frames = [1]

        scriptSrc = regenerateBlenderCropFile(self.scriptSrc, 8, 8, 0.0, 1.0, 0.0, 1.0)

        extra_data =          {      "pathRoot": self.mainSceneDir,
                                    "startTask" : 1,
                                    "endTask": 1,
                                    "totalTasks": self.totalTasks,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFile" : sceneFile,
                                    "scriptSrc": scriptSrc,
                                    "engine": self.engine,
                                    "frames": frames
                                }

        hash = "{}".format(random.getrandbits(128))

        self.testTaskResPath = getTestTaskPath(self.root_path)
        logger.debug(self.testTaskResPath)
        if not os.path.exists(self.testTaskResPath):
            os.makedirs(self.testTaskResPath)

        return self._newComputeTaskDef(hash, extra_data, workingDirectory, 0)

    #######################
    def _getPartSize(self) :
        if not self.useFrames:
            resY = int (math.floor(float(self.resY) / float(self.totalTasks)))
        elif len(self.frames) >= self.totalTasks:
            resY = self.resY
        else:
            parts = self.totalTasks / len(self.frames)
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
        startY = startBox[1]+ (extra_data['startTask'] - 1) * (self.resY / float(extra_data['totalTasks']))
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
            offset = int (math.floor((chunkNum - 1) * float(self.resY) / float(self.totalTasks)))
            imgOffset.paste(img, (0, offset))
        except Exception, err:
            logger.error("Can't generate preview {}".format(str(err)))

        tmpDir = getTmpPath(self.header.client_id, self.header.task_id, self.root_path)

        self.previewFilePath = "{}".format(os.path.join(tmpDir, "current_preview"))

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