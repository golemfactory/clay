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
    renderer.scene_fileExt   = [ "max",  "zip" ]
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
                                   self.taskDefinition.full_task_timeout,
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
                  presetFile,
                  cmdFile,
                  useFrames,
                  frames,
                  return_address = "",
                  return_port = 0,
                 ):

        FrameRenderingTask.__init__(self, client_id, task_id, return_address, return_port,
                          ThreeDSMaxEnvironment.get_id(), full_task_timeout, subtask_timeout,
                          mainProgramFile, taskResources, mainSceneDir, mainSceneFile,
                          total_tasks, resX, resY, outfilebasename, output_file, outputFormat,
                          root_path, estimated_memory, useFrames, frames)


        self.presetFile = presetFile
        self.cmd        = cmdFile
        self.framesGiven = {}

    #######################
    def query_extra_data(self, perf_index, num_cores = 0, client_id = None):

        if not self._acceptClient(client_id):
            logger.warning(" Client {} banned from this task ".format(client_id))
            return None

        start_task, end_task = self._getNextTask()

        working_directory = self._getWorkingDirectory()
        presetFile = self.__getPresetFileRelPath()
        scene_file = self._getSceneFileRelPath()
        cmdFile = os.path.basename(self.cmd)

        if self.useFrames:
            frames, parts = self._chooseFrames(self.frames, start_task, self.total_tasks)
        else:
            frames = []
            parts = 1

        extra_data =          {      "path_root" : self.mainSceneDir,
                                    "start_task" : start_task,
                                    "end_task" : end_task,
                                    "total_tasks" : self.total_tasks,
                                    "outfilebasename" : self.outfilebasename,
                                    "scene_file" : scene_file,
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
        self.subTasksGiven[ hash ]['perf'] = perf_index
        self.subTasksGiven[ hash ][ 'client_id' ] = client_id

        for frame in frames:
            self.framesGiven[ frame ] = {}

        if not self.useFrames:
            self._updateTaskPreview()
        else:
            self._updateFrameTaskPreview()

        return self._newComputeTaskDef(hash, extra_data, working_directory, perf_index)

    #######################
    def query_extra_dataForTestTask(self):

        working_directory = self._getWorkingDirectory()
        presetFile = self.__getPresetFileRelPath()
        scene_file = self._getSceneFileRelPath()
        cmdFile = os.path.basename(self.cmd)

        if self.useFrames:
            frames = [ self.frames[0] ]
        else:
            frames = []

        extra_data =          {      "path_root" : self.mainSceneDir,
                                    "start_task" : 1,
                                    "end_task" : 1,
                                    "total_tasks" : self.total_tasks,
                                    "outfilebasename" : self.outfilebasename,
                                    "scene_file" : scene_file,
                                    "width" : 1,
                                    "height": self.total_tasks,
                                    "presetFile": presetFile,
                                    "cmdFile": cmdFile,
                                    "num_cores": 0,
                                    "useFrames": self.useFrames,
                                    "frames": frames, 
                                    "parts": 1,
                                    "overlap": 0
                                }

        hash = "{}".format(random.getrandbits(128))

        self.test_taskResPath = getTestTaskPath(self.root_path)
        logger.debug(self.test_taskResPath)
        if not os.path.exists(self.test_taskResPath):
            os.makedirs(self.test_taskResPath)

        return self._newComputeTaskDef(hash, extra_data, working_directory, 0)


    #######################
    @checkSubtask_idWrapper
    def get_price_mod(self, subtask_id):
        perf =  (self.subTasksGiven[ subtask_id ]['end_task'] - self.subTasksGiven[ subtask_id ][ 'start_task' ]) + 1
        perf *= float(self.subTasksGiven[ subtask_id ]['perf']) / 1000
        perf *= 50
        return perf

    #######################
    @checkSubtask_idWrapper
    def restart_subtask(self, subtask_id):
        FrameRenderingTask.restart_subtask(self, subtask_id)
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
    def _short_extra_data_repr(self, perf_index, extra_data):
        l = extra_data
        msg = []
        msg.append("scene file: {} ".format(l [ "scene_file" ]))
        msg.append("preset: {} ".format(l [ "presetFile" ]))
        msg.append("total tasks: {}".format(l[ "total_tasks" ]))
        msg.append("start task: {}".format(l[ "start_task" ]))
        msg.append("end task: {}".format(l[ "end_task" ]))
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
        if not self.useFrames:
            startY = startBox[1] + (extra_data['start_task'] - 1) * self.resY / extra_data['total_tasks']
        elif self.total_tasks <= len(self.frames):
            startY = startBox[1]
            extra_data['frames'] = [ self.__getFrameNumFromOutputFile(trFile) ]
            extra_data['parts'] = extra_data['total_tasks']
        else:
            part = ((extra_data['start_task'] - 1) % extra_data['parts']) + 1
            startY = startBox[1] + (part - 1) * self.resY / extra_data['parts']
        extra_data['total_tasks'] = self.resY / self.verificationOptions.boxSize[1]
        extra_data['parts'] = extra_data['total_tasks']
        extra_data['start_task'] = startY / self.verificationOptions.boxSize[1]  + 1
        extra_data['end_task'] = (startY + self.verificationOptions.boxSize[1]) / self.verificationOptions.boxSize[1]  + 1
        extra_data['overlap'] = ((extra_data['end_task'] - extra_data['start_task']) * self.verificationOptions.boxSize[1])
        if extra_data['start_task'] != 1:
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