import logging
import os
import random
import math
import shutil

from collections import OrderedDict

from  examples.gnr.RenderingTaskState import RendererDefaults, RendererInfo
from  examples.gnr.task.GNRTask import GNROptions, checkSubtask_idWrapper
from  examples.gnr.task.RenderingTask import RenderingTask
from  examples.gnr.task.FrameRenderingTask import FrameRenderingTask, FrameRenderingTaskBuiler, get_taskBoarder, get_taskNumFromPixels
from  examples.gnr.RenderingDirManager import getTestTaskPath, getTmpPath

from examples.gnr.task.RenderingTaskCollector import exr_to_pil, RenderingTaskCollector
from examples.gnr.RenderingEnvironment import VRayEnvironment
from examples.gnr.ui.VRayDialog import VRayDialog
from examples.gnr.customizers.VRayDialogCustomizer import VRayDialogCustomizer
from golem.task.TaskState import SubtaskStatus

from PIL import Image, ImageChops

logger = logging.getLogger(__name__)

##############################################
def buildVRayRendererInfo():
    defaults = RendererDefaults()
    defaults.outputFormat = "EXR"
    defaults.mainProgramFile = os.path.normpath(os.path.join(os.environ.get('GOLEM'), 'examples/tasks/VRayTask.py'))
    defaults.minSubtasks = 1
    defaults.maxSubtasks = 100
    defaults.defaultSubtasks = 6

    renderer = RendererInfo("VRay Standalone", defaults, VRayTaskBuilder, VRayDialog, VRayDialogCustomizer, VRayRendererOptions)
    renderer.outputFormats = [ "BMP", "EPS", "EXR", "GIF", "IM", "JPEG", "PCX", "PDF", "PNG", "PPM", "TIFF" ]
    renderer.sceneFileExt = [ "vrscene" ]
    renderer.get_taskNumFromPixels = get_taskNumFromPixels
    renderer.get_taskBoarder = get_taskBoarder

    return renderer

##############################################
class VRayRendererOptions(GNROptions):

    #######################
    def __init__(self):
        self.environment = VRayEnvironment()
        self.rtEngine = 0
        self.rtEngineValues = {0: 'No engine', 1: 'CPU', 3: 'OpenGL', 5: 'CUDA' }
        self.useFrames = False
        self.frames = range(1, 11)

##############################################
class VRayTaskBuilder(FrameRenderingTaskBuiler):
    #######################
    def build(self):
        mainSceneDir = os.path.dirname(self.taskDefinition.mainSceneFile)

        vRayTask = VRayTask(      self.client_id,
                                   self.taskDefinition.task_id,
                                   mainSceneDir,
                                   self.taskDefinition.mainSceneFile,
                                   self.taskDefinition.mainProgramFile,
                                   self._calculateTotal(buildVRayRendererInfo(), self.taskDefinition),
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
                                   self.taskDefinition.rendererOptions.rtEngine,
                                   self.taskDefinition.rendererOptions.useFrames,
                                   self.taskDefinition.rendererOptions.frames
                                  )
        return self._setVerificationOptions(vRayTask)

##############################################
class VRayTask(FrameRenderingTask):
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
                  full_task_timeout,
                  subtask_timeout,
                  taskResources,
                  estimated_memory,
                  root_path,
                  rtEngine,
                  useFrames,
                  frames,
                  return_address = "",
                  return_port = 0,
                  key_id = ""):

        FrameRenderingTask.__init__(self, client_id, task_id, return_address, return_port, key_id,
                          VRayEnvironment.get_id(), full_task_timeout, subtask_timeout,
                          mainProgramFile, taskResources, mainSceneDir, mainSceneFile,
                          totalTasks, resX, resY, outfilebasename, output_file, outputFormat,
                          root_path, estimated_memory, useFrames, frames)

        self.rtEngine = rtEngine
        self.collectedAlphaFiles = {}

        self.framesParts = {}
        self.framesAlphaParts = {}


    #######################
    def query_extra_data(self, perf_index, num_cores = 0, client_id = None):

        if not self._acceptClient(client_id):
            logger.warning(" Client {} banned from this task ".format(client_id))
            return None


        startTask, endTask = self._getNextTask()

        working_directory = self._getWorkingDirectory()
        sceneFile = self._getSceneFileRelPath()

        if self.useFrames:
            frames, parts = self._chooseFrames(self.frames, startTask, self.totalTasks)
        else:
            frames = []
            parts = 1

        extra_data =          {      "pathRoot" : self.mainSceneDir,
                                    "startTask" : startTask,
                                    "endTask" : endTask,
                                    "hTask": self.totalTasks,
                                    "totalTasks" : self.totalTasks,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFile" : sceneFile,
                                    "width" : self.resX,
                                    "height": self.resY,
                                    "rtEngine": self.rtEngine,
                                    "numThreads": num_cores,
                                    "useFrames": self.useFrames,
                                    "frames": frames,
                                    "parts": parts
                                }


        hash = "{}".format(random.getrandbits(128))
        self.subTasksGiven[ hash ] = extra_data
        self.subTasksGiven[ hash ][ 'status' ] = SubtaskStatus.starting
        self.subTasksGiven[ hash ][ 'perf' ] = perf_index
        self.subTasksGiven[ hash ][ 'client_id' ] = client_id

        for frame in frames:
            if self.useFrames and frame not in self.framesParts:
                self.framesParts[ frame ] = {}
                self.framesAlphaParts[ frame ] = {}

        if not self.useFrames:
            self._updateTaskPreview()
        else:
            self._updateFrameTaskPreview()

        return self._newComputeTaskDef(hash, extra_data, working_directory, perf_index)

    #######################
    def query_extra_dataForTestTask(self):

        working_directory = self._getWorkingDirectory()
        sceneFile = self._getSceneFileRelPath()

        if self.useFrames:
            frames = [ self.frames[0] ]
        else:
            frames = []

        extra_data =          {      "pathRoot" : self.mainSceneDir,
                                    "startTask" : 0,
                                    "endTask" : 1,
                                    "hTask": self.totalTasks,
                                    "totalTasks" : self.totalTasks,
                                    "outfilebasename" : self.outfilebasename,
                                    "sceneFile" : sceneFile,
                                    "width" : 1,
                                    "height": 1,
                                    "rtEngine": self.rtEngine,
                                    "numThreads": 0,
                                    "useFrames": self.useFrames,
                                    "frames": frames,
                                    "parts": 1
                                }

        hash = "{}".format(random.getrandbits(128))

        self.test_taskResPath = getTestTaskPath(self.root_path)
        logger.debug(self.test_taskResPath)
        if not os.path.exists(self.test_taskResPath):
            os.makedirs(self.test_taskResPath)

        return self._newComputeTaskDef(hash, extra_data, working_directory, 0)

  #######################
    @checkSubtask_idWrapper
    def computation_finished(self, subtask_id, task_result, dir_manager = None, result_type = 0):

        if not self.shouldAccept(subtask_id):
            return

        tmpDir = dir_manager.get_task_temporary_dir(self.header.task_id, create = False)
        self.tmpDir = tmpDir

        if len(task_result) > 0:
            numStart = self.subTasksGiven[ subtask_id ][ 'startTask' ]
            parts = self.subTasksGiven[ subtask_id ][ 'parts' ]
            numEnd = self.subTasksGiven[ subtask_id ][ 'endTask' ]
            self.subTasksGiven[ subtask_id ][ 'status' ] = SubtaskStatus.finished

            if self.useFrames and self.totalTasks <= len(self.frames):
                if len(task_result) < len(self.subTasksGiven[ subtask_id ][ 'frames' ]):
                    self._markSubtaskFailed(subtask_id)
                    return

            trFiles = self.loadTaskResults(task_result, result_type, tmpDir)

            if not self._verifyImgs(subtask_id, trFiles):
                self._markSubtaskFailed(subtask_id)
                if not self.useFrames:
                    self._updateTaskPreview()
                else:
                    self._updateFrameTaskPreview()
                return

            self.countingNodes[ self.subTasksGiven[ subtask_id ][ 'client_id' ] ] = 1

            if not self.useFrames:
                for trFile in trFiles:
                    self.__collectImagePart(numStart, trFile)
            elif self.totalTasks < len(self.frames):
                for trFile in trFiles:
                    self.__collectFrameFile(trFile)
                self.__collectFrames(self.subTasksGiven[ subtask_id ][ 'frames' ], tmpDir)
            else:
                for trFile in trFiles:
                    self.__collectFramePart(numStart, trFile, parts, tmpDir)

            self.numTasksReceived += numEnd - numStart + 1
        else:
            self._markSubtaskFailed(subtask_id)
            if not self.useFrames:
                self._updateTaskPreview()
            else:
                self._updateFrameTaskPreview()

        if self.numTasksReceived == self.totalTasks:
            if self.useFrames:
                self.__copyFrames()
            else:
                output_file_name = u"{}".format(self.output_file, self.outputFormat)
                self.__putImageTogether(output_file_name)

    #######################
    @checkSubtask_idWrapper
    def get_price_mod(self, subtask_id):
        perf =  (self.subTasksGiven[ subtask_id ]['endTask'] - self.subTasksGiven[ subtask_id ][ 'startTask' ]) + 1
        perf *= float(self.subTasksGiven[ subtask_id ]['perf']) / 1000
        perf *= 10
        return perf

    #######################
    def _short_extra_data_repr(self, perf_index, extra_data):
        l = extra_data
        msg = []
        msg.append(" scene file: {} ".format(l [ "sceneFile" ]))
        msg.append("total tasks: {}".format(l[ "totalTasks" ]))
        msg.append("start task: {}".format(l[ "startTask" ]))
        msg.append("end task: {}".format(l[ "endTask" ]))
        msg.append("outfile basename: {}".format(l[ "outfilebasename" ]))
        msg.append("size: {}x{}".format(l[ "width" ], l[ "height" ]))
        msg.append("rtEngine: {}".format(l[ "rtEngine" ]))
        if l["useFrames"]:
            msg.append("frames: {}".format(l[ "frames" ]))
        return "\n".join(msg)

    #######################
    def _pasteNewChunk(self, imgChunk, previewFilePath, chunkNum, allChunksNum):
        if os.path.exists(previewFilePath):
            img = Image.open(previewFilePath)
            img = ImageChops.add(img, imgChunk)
            return img
        else:
            return imgChunk

    #######################
    @checkSubtask_idWrapper
    def _changeScope(self, subtask_id, startBox, trFile):
        extra_data, _ = FrameRenderingTask._changeScope(self, subtask_id, startBox, trFile)
        extra_data['isAlpha'] = self.__isAlphaFile(trFile)
        extra_data['generateStartBox'] = True
        if startBox[0] == 0:
            newStartBoxX = 0
            newBoxX = self.verificationOptions.boxSize[0] + 1
        else:
            newStartBoxX = startBox[0] - 1
            newBoxX = self.verificationOptions.boxSize[0] + 2
        if startBox[1] == 0:
            newStartBoxY = 0
            newBoxY = self.verificationOptions.boxSize[1] + 1
        else:
            newStartBoxY = startBox[1] - 1
            newBoxY = self.verificationOptions.boxSize[1] + 2
        extra_data['startBox'] = (newStartBoxX, newStartBoxY)
        extra_data['box'] = (newBoxX, newBoxY)
        if self.useFrames:
            extra_data['frames'] = [ self.__getFrameNumFromOutputFile(trFile) ]
            extra_data['parts'] = extra_data['totalTasks']


        return extra_data, startBox

    #######################
    def __getFrameNumFromOutputFile(self, file_):
        file_name = os.path.basename(file_)
        file_name, ext = os.path.splitext(file_name)
        idx = file_name.find(self.outfilebasename)
        if self.__isAlphaFile(file_name):
            idxAlpha = file_name.find("Alpha")
            if self.useFrames and self.totalTasks == len(self.frames):
                return int (file_name[ idx + len(self.outfilebasename) + 1: idxAlpha - 1])
            elif self.useFrames and self.totalTasks < len(self.frames):
                return int (file_name[ idxAlpha + len("Alpha") + 1: ])
            else:
                return int(file_name.split(".")[-3])

        else:
            if self.useFrames and self.totalTasks > len(self.frames):
                suf = file_name[ idx + len(self.outfilebasename) + 1:]
                idxDot = suf.find(".")
                return int (suf[ idxDot + 1: ])
            else:
                return int(file_name[ idx + len(self.outfilebasename) + 1:])


    #######################
    def __useAlpha(self):
        unsupportedFormats = ['BMP', 'PCX', 'PDF']
        if self.outputFormat in unsupportedFormats:
            return False
        return True


    #######################
    def __isAlphaFile(self, file_name):
        return file_name.find('Alpha') != -1

    #######################
    def __putImageTogether(self, output_file_name ):
        collector = RenderingTaskCollector()

        if not self._useOuterTaskCollector():
            for file in self.collectedFileNames.values():
                collector.addImgFile(file)
            for file in self.collectedAlphaFiles.values():
                collector.acceptAlphaFile(file)
            collector.finalize().save(output_file_name, self.outputFormat)
#            if not self.useFrames:
#                self.previewFilePath = output_file_name
        else:
            self.collectedFileNames = OrderedDict(sorted(self.collectedFileNames.items()))
            self.collectedAlphaFiles = OrderedDict(sorted(self.collectedAlphaFiles.items()))
            files = self.collectedFileNames.values() + self.collectedAlphaFiles.values()
            self._putCollectedFilesTogether(output_file_name, files, "add")

    #######################
    def __collectImagePart(self, numStart, trFile):
        if self.__isAlphaFile(trFile):
            self.collectedAlphaFiles[ numStart ] = trFile
        else:
            self.collectedFileNames[ numStart ] = trFile
            self._updatePreview(trFile)
            self._updateTaskPreview()

    #######################
    def __collectFrames(self, frames, tmpDir):
        for frame in frames:
            self.__putFrameTogether(tmpDir, frame, frame)


    #######################
    def __collectFrameFile(self, trFile):
        frameNum = self.__getFrameNumberFromName(trFile)
        if frameNum is None:
            return
        if self.__isAlphaFile(trFile):
            self.framesAlphaParts[ frameNum ][1] = trFile
        else:
            self.framesParts[ frameNum ][1] = trFile

    #######################
    def __collectFramePart(self, numStart, trFile, parts, tmpDir):
        frameNum = self.frames[(numStart - 1) / parts ]
        part = ((numStart - 1) % parts) + 1

        if self.__isAlphaFile(trFile):
            self.framesAlphaParts[ frameNum ][ part ] = trFile
        else:
            self.framesParts[ frameNum ][ part ] = trFile

        self._updateFramePreview(trFile, frameNum, part)

        if len(self.framesParts[ frameNum ]) == parts:
            self.__putFrameTogether(tmpDir, frameNum, numStart)

    #######################
    def __copyFrames(self):
        outpuDir = os.path.dirname(self.output_file)
        for file in self.collectedFileNames.values():
            shutil.copy(file, os.path.join(outpuDir, os.path.basename(file)))

    #######################
    def __putFrameTogether(self, tmpDir, frameNum, numStart):
        output_file_name = os.path.join(tmpDir, self.__getOutputName(frameNum))
        if self._useOuterTaskCollector():
            collected = self.framesParts[ frameNum ]
            collected = OrderedDict(sorted(collected.items()))
            collectedAlphas = self.framesAlphaParts[ frameNum ]
            collectedAlphas = OrderedDict(sorted(collectedAlphas.items()))
            files = collected.values() + collectedAlphas.values()
            self._putCollectedFilesTogether(output_file_name, files, "add")
        else:
            collector = RenderingTaskCollector()
            for part in self.framesParts[ frameNum ].values():
                collector.addImgFile(part)
            for part in self.framesAlphaParts[ frameNum ].values():
                collector.addAlphaFile(part)
            collector.finalize().save(output_file_name, self.outputFormat)
        self.collectedFileNames[ numStart ] = output_file_name
        self._updateFramePreview(output_file_name, frameNum, final=True)

    #######################
    def __getFrameNumberFromName(self, frameName):
        frameName, ext = os.path.splitext(frameName)
        try:
            num = int(frameName.split(".")[-1].lstrip("0"))
            return num
        except Exception, err:
            logger.warning("Wrong result name: {}; {} ", frameName, str(err))
            return None


    #######################
    def __getOutputName(self, frameNum):
        num = str(frameNum)
        return "{}{}.{}".format(self.outfilebasename, num.zfill(4), self.outputFormat)

    #######################
    def _runTask(self, src_code, scope):
        exec src_code in scope
        trFiles = self.loadTaskResults(scope['output']['data'], scope['output']['result_type'], self.tmpDir)
        if scope['isAlpha']:
            for trFile in trFiles:
                if self.__isAlphaFile(trFile):
                    return trFile
        else:
            for trFile in trFiles:
                if not self.__isAlphaFile(trFile):
                    return trFile
        if len(trFiles) > 0:
            return trFiles[0]
        else:
            return None



