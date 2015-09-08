import logging
import random
import os
import math

from PIL import Image, ImageChops

from golem.task.TaskState import SubtaskStatus

from examples.gnr.task.GNRTask import  GNROptions, checkSubtask_idWrapper
from examples.gnr.task.RenderingTaskCollector import exr_to_pil
from examples.gnr.task.FrameRenderingTask import FrameRenderingTask, FrameRenderingTaskBuiler, get_taskBoarder, get_taskNumFromPixels
from examples.gnr.RenderingDirManager import getTestTaskPath, getTmpPath
from examples.gnr.RenderingTaskState import RendererDefaults, RendererInfo
from examples.gnr.RenderingEnvironment import ThreeDSMaxEnvironment
from examples.gnr.ui.ThreeDSMaxDialog import ThreeDSMaxDialog
from examples.gnr.customizers.ThreeDSMaxDialogCustomizer import ThreeDSMaxDialogCustomizer

logger = logging.getLogger(__name__)

##############################################
def build3dsMaxRendererInfo():
    defaults = RendererDefaults()
    defaults.outputFormat       = "EXR"
    defaults.mainProgramFile    = os.path.normpath(os.path.join(os.environ.get('GOLEM'), 'examples/tasks/3dsMaxTask.py'))
    defaults.minSubtasks        = 1
    defaults.maxSubtasks        = 100
    defaults.defaultSubtasks    = 6

    renderer                = RendererInfo("3ds Max Renderer", defaults, ThreeDSMaxTaskBuilder, ThreeDSMaxDialog, ThreeDSMaxDialogCustomizer, ThreeDSMaxRendererOptions)
    renderer.outputFormats  = [ "BMP", "EXR", "GIF", "IM", "JPEG", "PCD", "PCX", "PNG", "PPM", "PSD", "TIFF", "XBM", "XPM" ]
    renderer.sceneFileExt   = [ "max",  "zip" ]
    renderer.get_taskNumFromPixels = get_taskNumFromPixels
    renderer.get_taskBoarder = get_taskBoarder

    return renderer

##############################################
class ThreeDSMaxRendererOptions (GNROptions):
    #######################
    def __init__(self):
        self.environment = ThreeDSMaxEnvironment()
        self.preset = self.environment.getDefaultPreset()
        self.cmd = self.environment.get3dsmaxcmdPath()
        self.useFrames = False
        self.frames = range(1, 11)

    #######################
    def addToResources(self, resources):
        if os.path.isfile(self.preset):
            resources.add(os.path.normpath(self.preset))
        return resources

    #######################
    def removeFromResources(self, resources):
        if os.path.normpath(self.preset) in resources:
            resources.remove(os.path.normpath(self.preset))
        return resources

##############################################
class ThreeDSMaxTaskBuilder(FrameRenderingTaskBuiler):
    #######################
    def build(self):
        mainSceneDir = os.path.dirname(self.taskDefinition.mainSceneFile)

        threeDSMaxTask = ThreeDSMaxTask(self.client_id,
                                   self.taskDefinition.task_id,
                                   mainSceneDir,
                                   self.taskDefinition.mainSceneFile,
                                   self.taskDefinition.mainProgramFile,
                                   self._calculateTotal(build3dsMaxRendererInfo(), self.taskDefinition),
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
                                   self.taskDefinition.rendererOptions.preset,
                                   self.taskDefinition.rendererOptions.cmd,
                                   self.taskDefinition.rendererOptions.useFrames,
                                   self.taskDefinition.rendererOptions.frames
                                  )

        return self._setVerificationOptions(threeDSMaxTask)


##############################################
class ThreeDSMaxTask(FrameRenderingTask):

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
                  presetFile,
                  cmdFile,
                  useFrames,
                  frames,
                  returnAddress = "",
                  returnPort = 0,
                 ):

        FrameRenderingTask.__init__(self, client_id, task_id, returnAddress, returnPort,
                          ThreeDSMaxEnvironment.getId(), fullTaskTimeout, subtask_timeout,
                          mainProgramFile, taskResources, mainSceneDir, mainSceneFile,
                          totalTasks, resX, resY, outfilebasename, output_file, outputFormat,
                          root_path, estimated_memory, useFrames, frames)


        self.presetFile = presetFile
        self.cmd        = cmdFile
        self.framesGiven = {}

    #######################
    def queryExtraData(self, perfIndex, num_cores = 0, client_id = None):

        if not self._acceptClient(client_id):
            logger.warning(" Client {} banned from this task ".format(client_id))
            return None

        startTask, endTask = self._getNextTask()

        workingDirectory = self._getWorkingDirectory()
        presetFile = self.__getPresetFileRelPath()
        sceneFile = self._getSceneFileRelPath()
        cmdFile = os.path.basename(self.cmd)

        if self.useFrames:
            frames, parts = self._chooseFrames(self.frames, startTask, self.totalTasks)
        else:
            frames = []
            parts = 1

        extra_data =          {      "pathRoot" : self.mainSceneDir,
                                    "startTask" : startTask,
                                    "endTask" : endTask,
                                    "totalTasks" : self.totalTasks,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFile" : sceneFile,
                                    "width" : self.resX,
                                    "height": self.resY,
                                    "presetFile": presetFile,
                                    "cmdFile": cmdFile,
                                    "num_cores": num_cores,
                                    "useFrames": self.useFrames,
                                    "frames": frames,
                                    "parts": parts,
                                    "overlap": 0
                                }



        hash = "{}".format(random.getrandbits(128))
        self.subTasksGiven[ hash ] = extra_data
        self.subTasksGiven[ hash ]['status' ] = SubtaskStatus.starting
        self.subTasksGiven[ hash ]['perf'] = perfIndex
        self.subTasksGiven[ hash ][ 'client_id' ] = client_id

        for frame in frames:
            self.framesGiven[ frame ] = {}

        if not self.useFrames:
            self._updateTaskPreview()
        else:
            self._updateFrameTaskPreview()

        return self._newComputeTaskDef(hash, extra_data, workingDirectory, perfIndex)

    #######################
    def queryExtraDataForTestTask(self):

        workingDirectory = self._getWorkingDirectory()
        presetFile = self.__getPresetFileRelPath()
        sceneFile = self._getSceneFileRelPath()
        cmdFile = os.path.basename(self.cmd)

        if self.useFrames:
            frames = [ self.frames[0] ]
        else:
            frames = []

        extra_data =          {      "pathRoot" : self.mainSceneDir,
                                    "startTask" : 1,
                                    "endTask" : 1,
                                    "totalTasks" : self.totalTasks,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFile" : sceneFile,
                                    "width" : 1,
                                    "height": self.totalTasks,
                                    "presetFile": presetFile,
                                    "cmdFile": cmdFile,
                                    "num_cores": 0,
                                    "useFrames": self.useFrames,
                                    "frames": frames, 
                                    "parts": 1,
                                    "overlap": 0
                                }

        hash = "{}".format(random.getrandbits(128))

        self.testTaskResPath = getTestTaskPath(self.root_path)
        logger.debug(self.testTaskResPath)
        if not os.path.exists(self.testTaskResPath):
            os.makedirs(self.testTaskResPath)

        return self._newComputeTaskDef(hash, extra_data, workingDirectory, 0)


    #######################
    @checkSubtask_idWrapper
    def getPriceMod(self, subtask_id):
        perf =  (self.subTasksGiven[ subtask_id ]['endTask'] - self.subTasksGiven[ subtask_id ][ 'startTask' ]) + 1
        perf *= float(self.subTasksGiven[ subtask_id ]['perf']) / 1000
        perf *= 50
        return perf

    #######################
    @checkSubtask_idWrapper
    def restartSubtask(self, subtask_id):
        FrameRenderingTask.restartSubtask(self, subtask_id)
        if not self.useFrames:
            self._updateTaskPreview()
        else:
            self._updateFrameTaskPreview()

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
    def _shortExtraDataRepr(self, perfIndex, extra_data):
        l = extra_data
        msg = []
        msg.append("scene file: {} ".format(l [ "sceneFile" ]))
        msg.append("preset: {} ".format(l [ "presetFile" ]))
        msg.append("total tasks: {}".format(l[ "totalTasks" ]))
        msg.append("start task: {}".format(l[ "startTask" ]))
        msg.append("end task: {}".format(l[ "endTask" ]))
        msg.append("outfile basename: {}".format(l[ "outfilebasename" ]))
        msg.append("size: {}x{}".format(l[ "width" ], l[ "height" ]))
        if l["useFrames"]:
            msg.append("frames: {}".format(l[ "frames" ]))
        return "\n".join(msg)


    #######################
    def _getOutputName(self, frameNum, numStart):
        num = str(frameNum)
        return "{}{}.{}".format(self.outfilebasename, num.zfill(4), self.outputFormat)

    #######################
    def __getPresetFileRelPath(self):
        presetFile = os.path.relpath(os.path.dirname(self.presetFile), os.path.dirname(self.mainProgramFile))
        presetFile = os.path.join(presetFile, os.path.basename(self.presetFile))
        return presetFile

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
        if not self.useFrames:
            startY = startBox[1] + (extra_data['startTask'] - 1) * self.resY / extra_data['totalTasks']
        elif self.totalTasks <= len(self.frames):
            startY = startBox[1]
            extra_data['frames'] = [ self.__getFrameNumFromOutputFile(trFile) ]
            extra_data['parts'] = extra_data['totalTasks']
        else:
            part = ((extra_data['startTask'] - 1) % extra_data['parts']) + 1
            startY = startBox[1] + (part - 1) * self.resY / extra_data['parts']
        extra_data['totalTasks'] = self.resY / self.verificationOptions.boxSize[1]
        extra_data['parts'] = extra_data['totalTasks']
        extra_data['startTask'] = startY / self.verificationOptions.boxSize[1]  + 1
        extra_data['endTask'] = (startY + self.verificationOptions.boxSize[1]) / self.verificationOptions.boxSize[1]  + 1
        extra_data['overlap'] = ((extra_data['endTask'] - extra_data['startTask']) * self.verificationOptions.boxSize[1])
        if extra_data['startTask'] != 1:
            newStartY = extra_data['overlap']
        else:
            newStartY = 0
        newStartY += startY % self.verificationOptions.boxSize[1]
        return extra_data, (startBox[0], newStartY)

    def __getFrameNumFromOutputFile(self, file_):
        file_name = os.path.basename(file_)
        file_name, ext = os.path.splitext(file_name)
        idx = file_name.find(self.outfilebasename)
        return int(file_name[ idx + len(self.outfilebasename):])