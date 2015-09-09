import os
import random
import logging
import math

from golem.task.TaskState import SubtaskStatus

from examples.gnr.RenderingEnvironment import PBRTEnvironment
from examples.gnr.RenderingDirManager import getTestTaskPath
from examples.gnr.RenderingTaskState import RendererDefaults, RendererInfo, RenderingTaskDefinition
from examples.gnr.task.SceneFileEditor import regeneratePbrtFile
from examples.gnr.task.GNRTask import GNROptions, GNRTaskBuilder
from examples.gnr.task.RenderingTask import RenderingTask, RenderingTaskBuilder
from examples.gnr.task.RenderingTaskCollector import RenderingTaskCollector
from examples.gnr.ui.PbrtDialog import PbrtDialog
from examples.gnr.customizers.PbrtDialogCustomizer import PbrtDialogCustomizer


logger = logging.getLogger(__name__)

##############################################
def buildPBRTRendererInfo():
    defaults = RendererDefaults()
    defaults.outputFormat       = "EXR"
    defaults.mainProgramFile    = os.path.normpath(os.path.join(os.environ.get('GOLEM'), 'examples/tasks/pbrtTask.py'))
    defaults.minSubtasks        = 4
    defaults.maxSubtasks        = 200
    defaults.defaultSubtasks    = 60


    renderer                = RendererInfo("PBRT", defaults, PbrtTaskBuilder, PbrtDialog, PbrtDialogCustomizer, PbrtRendererOptions)
    renderer.outputFormats  = [ "BMP", "EPS", "EXR", "GIF", "IM", "JPEG", "PCX", "PDF", "PNG", "PPM", "TIFF" ]
    renderer.scene_fileExt    = [ "pbrt" ]
    renderer.get_taskNumFromPixels = get_taskNumFromPixels
    renderer.get_taskBoarder = get_taskBoarder

    return renderer

##############################################
class PbrtRendererOptions( GNROptions):
    #######################
    def __init__(self):
        self.pbrtPath = ''
        self.pixelFilter = "mitchell"
        self.samplesPerPixelCount = 32
        self.algorithmType = "lowdiscrepancy"
        self.filters = [ "box", "gaussian", "mitchell", "sinc", "triangle" ]
        self.pathTracers = [ "adaptive", "bestcandidate", "halton", "lowdiscrepancy", "random", "stratified" ]

    #######################
    def addToResources(self, resources):
        if os.path.isfile(self.pbrtPath):
            resources.add(os.path.normpath(self.pbrtPath))
        return resources

    #######################
    def removeFromResources(self, resources):
        if os.path.normpath(self.pbrtPath) in resources:
            resources.remove(os.path.normpath(self.pbrtPath))
        return resources

##############################################
class PbrtGNRTaskBuilder(GNRTaskBuilder):
    def build(self):
        if isinstance(self.taskDefinition, RenderingTaskDefinition):
            rtd = self.taskDefinition
        else:
            rtd = self.__translateTaskDefinition()

        pbrtTaskBuilder = PbrtTaskBuilder(self.client_id, rtd, self.root_path)
        return pbrtTaskBuilder.build()

    def __translateTaskDefinition(self):
        rtd = RenderingTaskDefinition()
        rtd.task_id = self.taskDefinition.task_id
        rtd.full_task_timeout = self.taskDefinition.full_task_timeout
        rtd.subtask_timeout = self.taskDefinition.subtask_timeout
        rtd.min_subtask_time = self.taskDefinition.min_subtask_time
        rtd.resources = self.taskDefinition.resources
        rtd.estimated_memory = self.taskDefinition.estimated_memory
        rtd.totalSubtasks = self.taskDefinition.totalSubtasks
        rtd.optimizeTotal = self.taskDefinition.optimizeTotal
        rtd.mainProgramFile = self.taskDefinition.mainProgramFile
        rtd.taskType = self.taskDefinition.taskType
        rtd.verificationOptions = self.taskDefinition.verificationOptions

        rtd.resolution = self.taskDefinition.options.resolution
        rtd.renderer = self.taskDefinition.taskType
        rtd.mainSceneFile = self.taskDefinition.options.mainSceneFile
        rtd.resources.add(rtd.mainSceneFile)
        rtd.output_file = self.taskDefinition.options.output_file
        rtd.outputFormat = self.taskDefinition.options.outputFormat
        rtd.rendererOptions = PbrtRendererOptions()
        rtd.rendererOptions.pixelFilter = self.taskDefinition.options.pixelFilter
        rtd.rendererOptions.algorithmType = self.taskDefinition.options.algorithmType
        rtd.rendererOptions.samplesPerPixelCount = self.taskDefinition.options.samplesPerPixelCount
        rtd.rendererOptions.pbrtPath = self.taskDefinition.options.pbrtPath
        return rtd



##############################################
class PbrtTaskBuilder(RenderingTaskBuilder):
    #######################
    def build(self):
        mainSceneDir = os.path.dirname(self.taskDefinition.mainSceneFile)

        pbrtTask = PbrtRenderTask(self.client_id,
                                   self.taskDefinition.task_id,
                                   mainSceneDir,
                                   self.taskDefinition.mainProgramFile,
                                   self._calculateTotal(buildPBRTRendererInfo(), self.taskDefinition),
                                   20,
                                   4,
                                   self.taskDefinition.resolution[ 0 ],
                                   self.taskDefinition.resolution[ 1 ],
                                   self.taskDefinition.rendererOptions.pixelFilter,
                                   self.taskDefinition.rendererOptions.algorithmType,
                                   self.taskDefinition.rendererOptions.samplesPerPixelCount,
                                   self.taskDefinition.rendererOptions.pbrtPath,
                                   "temp",
                                   self.taskDefinition.mainSceneFile,
                                   self.taskDefinition.full_task_timeout,
                                   self.taskDefinition.subtask_timeout,
                                   self.taskDefinition.resources,
                                   self.taskDefinition.estimated_memory,
                                   self.taskDefinition.output_file,
                                   self.taskDefinition.outputFormat,
                                   self.root_path
                                 )

        return self._setVerificationOptions(pbrtTask)

    def _setVerificationOptions(self, newTask):
        newTask = RenderingTaskBuilder._setVerificationOptions(self, newTask)
        if newTask.advanceVerification:
            boxX = min(newTask.verificationOptions.boxSize[0], newTask.taskResX)
            boxY = min(newTask.verificationOptions.boxSize[1], newTask.taskResY)
            newTask.boxSize = (boxX, boxY)
        return newTask

    #######################
    def _calculateTotal(self, renderer, definition):

        if (not definition.optimizeTotal) and (renderer.defaults.minSubtasks <= definition.totalSubtasks <= renderer.defaults.maxSubtasks):
            return definition.totalSubtasks

        taskBase = 1000000
        allOp = definition.resolution[0] * definition.resolution[1] * definition.rendererOptions.samplesPerPixelCount
        return max(renderer.defaults.minSubtasks, min(renderer.defaults.maxSubtasks, allOp / taskBase))

def countSubtaskReg(total_tasks, subtasks, resX, resY):
    nx = total_tasks * subtasks
    ny = 1
    while (nx % 2 == 0) and (2 * resX * ny < resY * nx):
        nx /= 2
        ny *= 2
    taskResX = float(resX) / float(nx)
    taskResY = float(resY) / float(ny)
    return nx, ny, taskResX, taskResY

##############################################
class PbrtRenderTask(RenderingTask):

    #######################
    def __init__(self,
                  client_id,
                  task_id,
                  mainSceneDir,
                  mainProgramFile,
                  total_tasks,
                  num_subtasks,
                  num_cores,
                  resX,
                  resY,
                  pixelFilter,
                  sampler,
                  samplesPerPixel,
                  pbrtPath,
                  outfilebasename,
                  scene_file,
                  full_task_timeout,
                  subtask_timeout,
                  taskResources,
                  estimated_memory,
                  output_file,
                  outputFormat,
                  root_path,
                  return_address = "",
                  return_port = 0,
                  key_id = ""
                 ):


        RenderingTask.__init__(self, client_id, task_id, return_address, return_port, key_id,
                                PBRTEnvironment.get_id(), full_task_timeout, subtask_timeout,
                                mainProgramFile, taskResources, mainSceneDir, scene_file,
                                total_tasks, resX, resY, outfilebasename, output_file, outputFormat,
                                root_path, estimated_memory)

        self.collectedFileNames = set()

        self.num_subtasks        = num_subtasks
        self.num_cores           = num_cores

        try:
            with open(scene_file) as f:
                self.scene_fileSrc = f.read()
        except Exception, err:
            logger.error("Wrong scene file: {}".format(str(err)))
            self.scene_fileSrc = ""

        self.resX               = resX
        self.resY               = resY
        self.pixelFilter        = pixelFilter
        self.sampler            = sampler
        self.samplesPerPixel    = samplesPerPixel
        self.pbrtPath           = pbrtPath
        self.nx, self.ny, self.taskResX, self.taskResY = countSubtaskReg(self.total_tasks, self.num_subtasks, self.resX, self.resY)

    #######################
    def query_extra_data(self, perf_index, num_cores = 0, client_id = None):
        if not self._acceptClient(client_id):
            logger.warning(" Client {} banned from this task ".format(client_id))
            return None


        start_task, end_task = self._getNextTask(perf_index)
        if start_task is None or end_task is None:
            logger.error("Task already computed")
            return None

        if num_cores == 0:
            num_cores = self.num_cores

        working_directory = self._getWorkingDirectory()
        sceneSrc = regeneratePbrtFile(self.scene_fileSrc, self.resX, self.resY, self.pixelFilter,
                                   self.sampler, self.samplesPerPixel)

        sceneDir= os.path.dirname(self._getSceneFileRelPath())

        pbrtPath = self.__getPbrtRelPath()

        extra_data =          {      "path_root" : self.mainSceneDir,
                                    "start_task" : start_task,
                                    "end_task" : end_task,
                                    "total_tasks" : self.total_tasks,
                                    "num_subtasks" : self.num_subtasks,
                                    "num_cores" : num_cores,
                                    "outfilebasename" : self.outfilebasename,
                                    "scene_fileSrc" : sceneSrc,
                                    "sceneDir": sceneDir,
                                    "pbrtPath": pbrtPath
                                }

        hash = "{}".format(random.getrandbits(128))
        self.subTasksGiven[ hash ] = extra_data
        self.subTasksGiven[ hash ][ 'status' ] = SubtaskStatus.starting
        self.subTasksGiven[ hash ][ 'perf' ] = perf_index
        self.subTasksGiven[ hash ][ 'client_id' ] = client_id

        self._updateTaskPreview()

        return self._newComputeTaskDef(hash, extra_data, working_directory, perf_index)

    #######################
    def query_extra_dataForTestTask(self):

        working_directory = self._getWorkingDirectory()

        sceneSrc = regeneratePbrtFile(self.scene_fileSrc, 1, 1, self.pixelFilter, self.sampler,
                                   self.samplesPerPixel)

        pbrtPath = self.__getPbrtRelPath()
        sceneDir= os.path.dirname(self._getSceneFileRelPath())

        extra_data =          {      "path_root" : self.mainSceneDir,
                                    "start_task" : 0,
                                    "end_task" : 1,
                                    "total_tasks" : self.total_tasks,
                                    "num_subtasks" : self.num_subtasks,
                                    "num_cores" : self.num_cores,
                                    "outfilebasename" : self.outfilebasename,
                                    "scene_fileSrc" : sceneSrc,
                                    "sceneDir": sceneDir,
                                    "pbrtPath": pbrtPath
                                }

        hash = "{}".format(random.getrandbits(128))

        self.test_taskResPath = getTestTaskPath(self.root_path)
        logger.debug(self.test_taskResPath)
        if not os.path.exists(self.test_taskResPath):
            os.makedirs(self.test_taskResPath)

        return self._newComputeTaskDef(hash, extra_data, working_directory, 0)

    #######################
    def computation_finished(self, subtask_id, task_result, dir_manager = None, result_type = 0):

        if not self.shouldAccept(subtask_id):
            return

        tmp_dir = dir_manager.get_task_temporary_dir(self.header.task_id, create = False)
        self.tmp_dir = tmp_dir
        trFiles = self.load_taskResults(task_result, result_type, tmp_dir)

        if not self._verifyImgs(subtask_id, trFiles):
            self._markSubtaskFailed(subtask_id)
            self._updateTaskPreview()
            return

        if len(task_result) > 0:
            self.subTasksGiven[ subtask_id ][ 'status' ] = SubtaskStatus.finished
            for trFile in trFiles:

                self.collectedFileNames.add(trFile)
                self.num_tasks_received += 1
                self.counting_nodes[ self.subTasksGiven[ subtask_id ][ 'client_id' ] ] = 1

                self._updatePreview(trFile)
                self._updateTaskPreview()
        else:
            self._markSubtaskFailed(subtask_id)
            self._updateTaskPreview()

        if self.num_tasks_received == self.total_tasks:
            output_file_name = u"{}".format(self.output_file, self.outputFormat)
            if self.outputFormat != "EXR":
                collector = RenderingTaskCollector()
                for file in self.collectedFileNames:
                    collector.addImgFile(file)
                collector.finalize().save(output_file_name, self.outputFormat)
                self.previewFilePath = output_file_name
            else:
                self._putCollectedFilesTogether(output_file_name, list(self.collectedFileNames), "add")

    #######################
    def restart(self):
        RenderingTask.restart(self)
        self.collectedFileNames = set()

    #######################
    def restart_subtask(self, subtask_id):
        if self.subTasksGiven[ subtask_id ][ 'status' ] == SubtaskStatus.finished:
            self.num_tasks_received += 1
        RenderingTask.restart_subtask(self, subtask_id)
        self._updateTaskPreview()

    #######################
    def get_price_mod(self, subtask_id):
        if subtask_id not in self.subTasksGiven:
            logger.error("Not my subtask {}".format(subtask_id))
            return 0
        perf =  (self.subTasksGiven[ subtask_id ]['end_task'] - self.subTasksGiven[ subtask_id ][ 'start_task' ])
        perf *= float(self.subTasksGiven[ subtask_id ]['perf']) / 1000
        return perf

    #######################
    def _getNextTask(self, perf_index):
        if self.lastTask != self.total_tasks :
            perf = max(int(float(perf_index) / 1500), 1)
            end_task = min(self.lastTask + perf, self.total_tasks)
            start_task = self.lastTask
            self.lastTask = end_task
            return start_task, end_task
        else:
            for sub in self.subTasksGiven.values():
                if sub['status'] == SubtaskStatus.failure:
                    sub['status'] = SubtaskStatus.resent
                    end_task = sub['end_task']
                    start_task = sub['start_task']
                    self.numFailedSubtasks -= 1
                    return start_task, end_task
        return None, None

    #######################
    def _short_extra_data_repr(self, perf_index, extra_data):
        l = extra_data
        return "path_root: {}, start_task: {}, end_task: {}, total_tasks: {}, num_subtasks: {}, num_cores: {}, outfilebasename: {}, scene_fileSrc: {}".format(l["path_root"], l["start_task"], l["end_task"], l["total_tasks"], l["num_subtasks"], l["num_cores"], l["outfilebasename"], l["scene_fileSrc"])

    #######################
    def _getPartImgSize(self, subtask_id, advTestFile):
        if advTestFile is not None:
            numTask = self.__getNumFromFileName(advTestFile[0], subtask_id)
        else:
            numTask = self.subTasksGiven[ subtask_id ][ 'start_task' ]
        numSubtask = random.randint(0, self.num_subtasks - 1)
        num = numTask * self.num_subtasks + numSubtask
        x0 = int( round((num % self.nx) * self.taskResX))
        x1 = int( round(((num % self.nx) + 1) * self.taskResX))
        y0 = int(math.floor((num / self.nx) * self.taskResY))
        y1 = int (math.floor(((num / self.nx) + 1) * self.taskResY))
        return x0, y0, x1, y1

    #######################
    def _markTaskArea(self, subtask, imgTask, color):
        for numTask in range(subtask['start_task'], subtask['end_task']):
            for sb in range(0, self.num_subtasks):
                num = self.num_subtasks * numTask + sb
                tx = num % self.nx
                ty = num /  self.nx
                xL = tx * self.taskResX
                xR = (tx + 1) * self.taskResX
                yL = ty * self.taskResY
                yR = (ty + 1) * self.taskResY

                for i in range(int(round(xL)) , int(round(xR))):
                    for j in range(int(math.floor(yL)) , int(math.floor(yR))) :
                        imgTask.putpixel((i, j), color)

    #######################
    def _changeScope(self, subtask_id, startBox, trFile):
        extra_data, startBox = RenderingTask._changeScope(self, subtask_id, startBox, trFile)
        extra_data[ "outfilebasename" ] = str(extra_data[ "outfilebasename" ])
        extra_data[ "resourcePath" ] = os.path.dirname(self.mainProgramFile)
        extra_data[ "tmp_path" ] = self.tmp_dir
        extra_data[ "total_tasks" ] = self.total_tasks * self.num_subtasks
        extra_data[ "num_subtasks" ] = 1
        extra_data[ "start_task" ] = get_taskNumFromPixels(startBox[0], startBox[1], extra_data[ "total_tasks" ], self.resX, self.resY, 1) - 1
        extra_data[ "end_task" ] = extra_data[ "start_task" ] + 1

        return extra_data, startBox

    def __getPbrtRelPath(self):
        pbrtRel = os.path.relpath(os.path.dirname(self.pbrtPath), os.path.dirname(self.mainSceneFile))
        pbrtRel = os.path.join(pbrtRel, os.path.basename(self.pbrtPath))
        return pbrtRel


    #######################
    def __getNumFromFileName(self, file_, subtask_id):
        try:
            file_name = os.path.basename(file_)
            file_name, ext = os.path.splitext(file_name)
            BASENAME = "temp"
            idx = file_name.find(BASENAME)
            return int(file_name[idx + len(BASENAME):])
        except Exception, err:
            logger.error("Wrong output file name {}: {}".format(file_, str(err)))
            return self.subTasksGiven[ subtask_id ][ 'start_task' ]

#####################################################################
def get_taskNumFromPixels(pX, pY, total_tasks, resX = 300, resY = 200, subtasks = 20):
    nx, ny, taskResX, taskResY = countSubtaskReg(total_tasks, subtasks, resX, resY)
    numX = int(math.floor(pX / taskResX))
    numY = int(math.floor(pY / taskResY))
    num = (numY * nx + numX) /subtasks + 1
    return num

#####################################################################
def get_taskBoarder(start_task, end_task, total_tasks, resX = 300, resY = 200, num_subtasks = 20):
    boarder = []
    newLeft = True
    lastRight = None
    for numTask in range(start_task, end_task):
        for sb in range(num_subtasks):
            num = num_subtasks * numTask + sb
            nx, ny, taskResX, taskResY = countSubtaskReg(total_tasks, num_subtasks, resX, resY)
            tx = num % nx
            ty = num /  nx
            xL = int(round(tx * taskResX))
            xR = int (round((tx + 1) * taskResX))
            yL = int (round(ty * taskResY))
            yR = int(round((ty + 1) * taskResY))
            for i in range(xL, xR):
                if (i, yL) in boarder:
                    boarder.remove((i, yL))
                else:
                    boarder.append((i, yL))
                boarder.append((i, yR))
            if xL == 0:
                newLeft = True
            if newLeft:
                for i in range(yL, yR):
                    boarder.append((xL, i))
                newLeft = False
            if xR == resY:
                for i in range(yL, yR):
                    boarder.append((xR, i))
            lastRight = (xR, yL, yR)
    xR, yL, yR = lastRight
    for i in range(yL, yR):
        boarder.append((xR, i))
    return boarder

