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

from examples.gnr.task.GNRTask import GNROptions, checkSubtaskIdWrapper
from examples.gnr.task.FrameRenderingTask import FrameRenderingTask, FrameRenderingTaskBuiler, getTaskBoarder, getTaskNumFromPixels
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
    renderer.getTaskNumFromPixels = getTaskNumFromPixels
    renderer.getTaskBoarder = getTaskBoarder

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

        vRayTask = BlenderRenderTask(      self.clientId,
                                   self.taskDefinition.taskId,
                                   mainSceneDir,
                                   self.taskDefinition.mainSceneFile,
                                   self.taskDefinition.mainProgramFile,
                                   self._calculateTotal(buildBlenderRendererInfo(), self.taskDefinition),
                                   self.taskDefinition.resolution[0],
                                   self.taskDefinition.resolution[1],
                                   os.path.splitext(os.path.basename(self.taskDefinition.outputFile))[0],
                                   self.taskDefinition.outputFile,
                                   self.taskDefinition.outputFormat,
                                   self.taskDefinition.fullTaskTimeout,
                                   self.taskDefinition.subtaskTimeout,
                                   self.taskDefinition.resources,
                                   self.taskDefinition.estimatedMemory,
                                   self.rootPath,
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
                  clientId,
                  taskId,
                  mainSceneDir,
                  mainSceneFile,
                  mainProgramFile,
                  totalTasks,
                  resX,
                  resY,
                  outfilebasename,
                  outputFile,
                  outputFormat,
                  fullTaskTimeout,
                  subtaskTimeout,
                  taskResources,
                  estimatedMemory,
                  rootPath,
                  useFrames,
                  frames,
                  engine,
                  returnAddress = "",
                  returnPort = 0,
                  keyId = ""):

        FrameRenderingTask.__init__(self, clientId, taskId, returnAddress, returnPort, keyId,
                          BlenderEnvironment.getId(), fullTaskTimeout, subtaskTimeout,
                          mainProgramFile, taskResources, mainSceneDir, mainSceneFile,
                          totalTasks, resX, resY, outfilebasename, outputFile, outputFormat,
                          rootPath, estimatedMemory, useFrames, frames)

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
    def queryExtraData(self, perfIndex, numCores = 0, clientId = None):

        if not self._acceptClient(clientId):
            logger.warning(" Client {} banned from this task ".format(clientId))
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
        extraData =          {      "pathRoot": self.mainSceneDir,
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
        self.subTasksGiven[ hash ] = extraData
        self.subTasksGiven[ hash ][ 'status' ] = SubtaskStatus.starting
        self.subTasksGiven[ hash ][ 'perf' ] = perfIndex
        self.subTasksGiven[ hash ][ 'clientId' ] = clientId
        self.subTasksGiven[ hash ][ 'parts' ] = parts


        if not self.useFrames:
            self._updateTaskPreview()
        else:
            self._updateFrameTaskPreview()

        return self._newComputeTaskDef(hash, extraData, workingDirectory, perfIndex)

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

        extraData =          {      "pathRoot": self.mainSceneDir,
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

        self.testTaskResPath = getTestTaskPath(self.rootPath)
        logger.debug(self.testTaskResPath)
        if not os.path.exists(self.testTaskResPath):
            os.makedirs(self.testTaskResPath)

        return self._newComputeTaskDef(hash, extraData, workingDirectory, 0)

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
    @checkSubtaskIdWrapper
    def _getPartImgSize(self, subtaskId, advTestFile) :
        x, y = self._getPartSize()
        return 0, 0, x, y

    #######################
    @checkSubtaskIdWrapper
    def _changeScope(self, subtaskId, startBox, trFile):
        extraData, _ = FrameRenderingTask._changeScope(self, subtaskId, startBox, trFile)
        minX = startBox[0]/float(self.resX)
        maxX = (startBox[0] + self.verificationOptions.boxSize[0] + 1) / float(self.resX)
        startY = startBox[1]+ (extraData['startTask'] - 1) * (self.resY / float(extraData['totalTasks']))
        maxY = float(self.resY - startY) /self.resY
        minY = max(float(self.resY - startY - self.verificationOptions.boxSize[1] - 1) /self.resY, 0.0)
        scriptSrc = regenerateBlenderCropFile(self.scriptSrc, self.resX, self.resY, minX, maxX, minY, maxY)
        extraData['scriptSrc'] = scriptSrc
        return extraData, (0, 0)

    def __getFrameNumFromOutputFile(self, file_):
        fileName = os.path.basename(file_)
        fileName, ext = os.path.splitext(fileName)
        idx = fileName.find(self.outfilebasename)
        return int(fileName[ idx + len(self.outfilebasename):])

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

        tmpDir = getTmpPath(self.header.clientId, self.header.taskId, self.rootPath)

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