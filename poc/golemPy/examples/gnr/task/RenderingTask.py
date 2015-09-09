import os
import logging
import subprocess
import math
import random
import uuid
from copy import deepcopy, copy
from PIL import Image, ImageChops

from golem.task.TaskState import SubtaskStatus
from golem.task.TaskBase import ComputeTaskDef
from golem.core.simpleexccmd import is_windows, exec_cmd

from examples.gnr.RenderingDirManager import getTmpPath
from examples.gnr.RenderingTaskState import AdvanceRenderingVerificationOptions
from examples.gnr.task.RenderingTaskCollector import exr_to_pil
from examples.gnr.task.ImgRepr import verifyImg, advanceVerifyImg
from examples.gnr.task.GNRTask import GNRTask, GNRTaskBuilder, checkSubtask_idWrapper

MIN_TIMEOUT = 2200.0
SUBTASK_TIMEOUT = 220.0

logger = logging.getLogger(__name__)
##############################################

class RenderingTaskBuilder(GNRTaskBuilder):
    def _calculateTotal (self, renderer, definition):
        if definition.optimizeTotal:
            return renderer.defaults.defaultSubtasks

        if renderer.defaults.minSubtasks <= definition.totalSubtasks <= renderer.defaults.maxSubtasks:
            return definition.totalSubtasks
        else :
            return renderer.defaults.defaultSubtasks

    def _setVerificationOptions(self, newTask):
        if self.taskDefinition.verificationOptions is None:
            newTask.advanceVerification = False
        else:
            newTask.advanceVerification = True
            newTask.verificationOptions = AdvanceRenderingVerificationOptions()
            newTask.verificationOptions.type = self.taskDefinition.verificationOptions.type
            newTask.verificationOptions.boxSize = (self.taskDefinition.verificationOptions.boxSize[0], (self.taskDefinition.verificationOptions.boxSize[1] / 2) * 2)
            newTask.verificationOptions.probability = self.taskDefinition.verificationOptions.probability
        return newTask


##############################################
class RenderingTask(GNRTask):
    #######################
    def __init__(self, client_id, task_id, owner_address, owner_port, ownerKeyId, environment, ttl,
                  subtaskTtl, mainProgramFile, taskResources, mainSceneDir, mainSceneFile,
                  total_tasks, resX, resY, outfilebasename, output_file, outputFormat, root_path,
                  estimated_memory):

        try:
            with open(mainProgramFile, "r") as src_file:
                src_code = src_file.read()
        except Exception, err:
            logger.error("Wrong main program file: {}".format(str(err)))
            src_code = ""

        resource_size = 0
        taskResources = set(filter(os.path.isfile, taskResources))
        for resource in taskResources:
            resource_size += os.stat(resource).st_size

        GNRTask.__init__(self, src_code, client_id, task_id, owner_address, owner_port, ownerKeyId, environment,
                          ttl, subtaskTtl, resource_size, estimated_memory)

        self.full_task_timeout        = ttl
        self.header.ttl             = self.full_task_timeout
        self.header.subtask_timeout  = subtaskTtl

        self.mainProgramFile        = mainProgramFile
        self.mainSceneFile          = mainSceneFile
        self.mainSceneDir           = mainSceneDir
        self.outfilebasename        = outfilebasename
        self.output_file             = output_file
        self.outputFormat           = outputFormat

        self.total_tasks             = total_tasks
        self.resX                   = resX
        self.resY                   = resY

        self.root_path               = root_path
        self.previewFilePath        = None
        self.previewTaskFilePath    = None

        self.taskResources          = deepcopy(taskResources)

        self.collectedFileNames     = {}

        self.advanceVerification    = False
        self.verifiedClients        = set()

        if is_windows():
            self.__get_path = self.__get_path_windows

    #######################
    def restart(self):
        GNRTask.restart(self)
        self.previewFilePath = None
        self.previewTaskFilePath = None

        self.collectedFileNames = {}

    #######################
    def update_task_state(self, task_state):
        if not self.finishedComputation() and self.previewTaskFilePath:
            task_state.extra_data['resultPreview'] = self.previewTaskFilePath
        elif self.previewFilePath:
            task_state.extra_data['resultPreview'] = self.previewFilePath

    #######################
    @checkSubtask_idWrapper
    def computation_failed(self, subtask_id):
        GNRTask.computation_failed(self, subtask_id)
        self._updateTaskPreview()

    #######################
    @checkSubtask_idWrapper
    def restart_subtask(self, subtask_id):
        if subtask_id in self.subTasksGiven:
            if self.subTasksGiven[ subtask_id ][ 'status' ] == SubtaskStatus.finished:
                self._removeFromPreview(subtask_id)
        GNRTask.restart_subtask(self, subtask_id)

    #####################
    def getPreviewFilePath(self):
        return self.previewFilePath

    #######################
    def _getPartSize(self):
        return self.resX, self.resY

    #######################
    @checkSubtask_idWrapper
    def _getPartImgSize(self, subtask_id, advTestFile):
        numTask = self.subTasksGiven[ subtask_id ][ 'start_task' ]
        imgHeight = int (math.floor(float(self.resY) / float(self.total_tasks)))
        return 0, (numTask - 1) * imgHeight, self.resX, numTask * imgHeight



    #######################
    def _updatePreview(self, newChunkFilePath):

        if newChunkFilePath.endswith(".exr"):
            img = exr_to_pil(newChunkFilePath)
        else:
            img = Image.open(newChunkFilePath)

        imgCurrent = self._openPreview()
        imgCurrent = ImageChops.add(imgCurrent, img)
        imgCurrent.save(self.previewFilePath, "BMP")

    #######################
    @checkSubtask_idWrapper
    def _removeFromPreview(self, subtask_id):
        emptyColor = (0, 0, 0)
        if isinstance(self.previewFilePath, list): #FIXME
            return
        img = self._openPreview()
        self._markTaskArea(self.subTasksGiven[ subtask_id ], img, emptyColor)
        img.save(self.previewFilePath, "BMP")

    #######################
    def _updateTaskPreview(self):
        sentColor = (0, 255, 0)
        failedColor = (255, 0, 0)

        tmp_dir = getTmpPath(self.header.client_id, self.header.task_id, self.root_path)
        self.previewTaskFilePath = "{}".format(os.path.join(tmp_dir, "current_task_preview"))

        imgTask = self._openPreview()

        for sub in self.subTasksGiven.values():
            if sub['status'] == SubtaskStatus.starting:
                self._markTaskArea(sub, imgTask, sentColor)
            if sub['status'] == SubtaskStatus.failure:
                self._markTaskArea(sub, imgTask, failedColor)

        imgTask.save(self.previewTaskFilePath, "BMP")

    #######################
    def _markTaskArea(self, subtask, imgTask, color):
        upper = int(math.floor(float(self.resY) / float(self.total_tasks)   * (subtask[ 'start_task' ] - 1)))
        lower = int(math.floor(float(self.resY) / float(self.total_tasks)  * (subtask[ 'end_task' ])))
        for i in range(0, self.resX):
            for j in range(upper, lower):
                imgTask.putpixel((i, j), color)


    #######################
    def _putCollectedFilesTogether(self, output_file_name, files, arg):
        if is_windows():
            taskCollectorPath = os.path.normpath(os.path.join(os.environ.get('GOLEM'), "tools/taskcollector/Release/taskcollector.exe"))
        else:
            taskCollectorPath = os.path.normpath(os.path.join(os.environ.get('GOLEM'), "tools/taskcollector/Release/taskcollector"))
        cmd = [ "{}".format(taskCollectorPath), "{}".format(arg), "{}".format(output_file_name) ] + files
        logger.debug(cmd)
        exec_cmd(cmd)

    #######################
    def _newComputeTaskDef(self, hash, extra_data, working_directory, perf_index):
        ctd = ComputeTaskDef()
        ctd.task_id              = self.header.task_id
        ctd.subtask_id           = hash
        ctd.extra_data           = extra_data
        ctd.return_address       = self.header.task_owner_address
        ctd.return_port          = self.header.task_owner_port
        ctd.task_owner           = self.header.task_owner
        ctd.short_description    = self._short_extra_data_repr(perf_index, extra_data)
        ctd.src_code             = self.src_code
        ctd.performance         = perf_index
        ctd.working_directory    = working_directory
        return ctd

    #######################
    def _getNextTask(self):
        if self.lastTask != self.total_tasks:
            self.lastTask += 1
            start_task = self.lastTask
            end_task = self.lastTask
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
    def _getWorkingDirectory(self):
        commonPathPrefix = os.path.commonprefix(self.taskResources)
        commonPathPrefix = os.path.dirname(commonPathPrefix)
        working_directory    = os.path.relpath(self.mainProgramFile, commonPathPrefix)
        working_directory    = os.path.dirname(working_directory)
        logger.debug("Working directory {}".format(working_directory))
        return self.__get_path(working_directory)


    #######################
    def _getSceneFileRelPath(self):
        scene_file = os.path.relpath(os.path.dirname(self.mainSceneFile) , os.path.dirname(self.mainProgramFile))
        scene_file = os.path.normpath(os.path.join(scene_file, os.path.basename(self.mainSceneFile)))
        return self.__get_path(scene_file)

    ########################
    def _short_extra_data_repr(self, perf_index, extra_data):
        l = extra_data
        return "path_root: {}, start_task: {}, end_task: {}, total_tasks: {}, outfilebasename: {}, scene_file: {}".format(
            l["path_root"], l["start_task"], l["end_task"], l["total_tasks"], l["outfilebasename"], l["scene_file"])

    #######################
    def _verifyImg(self, file_, resX, resY):
        return verifyImg(file_, resX, resY)

    #######################
    def _openPreview(self):
        tmp_dir = getTmpPath(self.header.client_id, self.header.task_id, self.root_path)

        if self.previewFilePath is None or not os.path.exists(self.previewFilePath):
            self.previewFilePath = "{}".format(os.path.join(tmp_dir, "current_preview"))
            img = Image.new("RGB", (self.resX,self.resY))
            img.save(self.previewFilePath, "BMP")

        return Image.open(self.previewFilePath)

    #######################
    def _useOuterTaskCollector(self):
        unsupportedFormats = ['EXR', 'EPS', 'exr', 'eps']
        if self.outputFormat in unsupportedFormats:
            return True
        return False

    #######################
    def _acceptClient(self, client_id):
        if client_id in self.counting_nodes:
            if self.counting_nodes[ client_id ] > 0: # client with accepted task
                return True
            elif self.counting_nodes[ client_id ] == 0: # client took task but hasn't return result yet
                self.counting_nodes[ client_id ] = -1
                return True
            else:
                self.counting_nodes[ client_id ] = -1 # client with failed task or client that took more than one task without returning any results
                return False
        else:
            self.counting_nodes[ client_id ] = 0
            return True #new node

    #######################
    @checkSubtask_idWrapper
    def __useAdvVerification(self, subtask_id):
        if self.verificationOptions.type == 'forAll':
            return True
        if self.verificationOptions.type == 'forFirst'and self.subTasksGiven[subtask_id]['client_id'] not in self.verifiedClients:
            return True
        if self.verificationOptions.type == 'random' and random.random() < self.verificationOptions.probability:
            return True
        return False

    #######################
    def _chooseAdvVerFile(self, trFiles, subtask_id):
        advTestFile = None
        if self.advanceVerification:
            if self.__useAdvVerification(subtask_id):
                advTestFile = random.sample(trFiles, 1)
        return advTestFile

    #######################
    @checkSubtask_idWrapper
    def _verifyImgs(self, subtask_id, trFiles):
        resX, resY = self._getPartSize()

        advTestFile = self._chooseAdvVerFile(trFiles, subtask_id)
        x0, y0, x1, y1 = self._getPartImgSize(subtask_id, advTestFile)

        for trFile in trFiles:
            if advTestFile is not None and trFile in advTestFile:
                startBox = self._getBoxStart(x0, y0, x1, y1)
                logger.debug('testBox: {}'.format(startBox))
                cmpFile, cmpStartBox = self._getCmpFile(trFile, startBox, subtask_id)
                logger.debug('cmpStarBox {}'.format(cmpStartBox))
                if not advanceVerifyImg(trFile, resX, resY, startBox, self.verificationOptions.boxSize, cmpFile, cmpStartBox):
                    return False
                else:
                    self.verifiedClients.add(self.subTasksGiven[subtask_id][ 'client_id' ])
            if not self._verifyImg(trFile, resX, resY):
                return False

        return True

    #######################
    def _getCmpFile(self, trFile, startBox, subtask_id):
        extra_data, newStartBox = self._changeScope(subtask_id, startBox, trFile)
        cmpFile = self._run_task(self.src_code, extra_data)
        return cmpFile, newStartBox

    #######################
    def _getBoxStart(self, x0, y0, x1, y1):
        verX = min(self.verificationOptions.boxSize[0], x1)
        verY = min(self.verificationOptions.boxSize[1], y1)
        startX = random.randint(x0, x1 - verX)
        startY = random.randint(y0, y1 - verY)
        return (startX, startY)

    #######################
    @checkSubtask_idWrapper
    def _changeScope(self, subtask_id, startBox, trFile):
        extra_data = copy(self.subTasksGiven[ subtask_id ])
        extra_data['outfilebasename'] = uuid.uuid4()
        extra_data['tmp_path'] = os.path.join(self.tmp_dir, str(self.subTasksGiven[subtask_id]['start_task']))
        if not os.path.isdir(extra_data['tmp_path']):
            os.mkdir(extra_data['tmp_path'])
        return extra_data, startBox

    #######################
    def _run_task(self, src_code, scope):
        exec src_code in scope
        if len(scope['output']) > 0:
            return self.load_taskResults(scope['output']['data'], scope['output']['result_type'], self.tmp_dir)[0]
        else:
            return None

    #######################
    def __get_path(self, path):
        return path

    #######################
    def __get_path_windows(self, path):
        return path.replace("\\", "/")