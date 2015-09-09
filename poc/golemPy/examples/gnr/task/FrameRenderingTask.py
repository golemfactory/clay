import os
import logging
import math
import shutil

from collections import OrderedDict
from PIL import Image, ImageChops

from examples.gnr.task.GNRTask import checkSubtask_idWrapper
from examples.gnr.task.RenderingTask import RenderingTask, RenderingTaskBuilder
from examples.gnr.task.RenderingTaskCollector import exr_to_pil, RenderingTaskCollector
from examples.gnr.RenderingDirManager import getTmpPath

from golem.task.TaskState import SubtaskStatus


logger = logging.getLogger(__name__)

##############################################
class FrameRenderingTaskBuiler(RenderingTaskBuilder):
    #######################
    def _calculateTotal(self, renderer, definition):
        if definition.optimizeTotal:
            if self.taskDefinition.rendererOptions.useFrames:
                return len(self.taskDefinition.rendererOptions.frames)
            else:
                return renderer.defaults.defaultSubtasks

        if self.taskDefinition.rendererOptions.useFrames:
            numFrames = len(self.taskDefinition.rendererOptions.frames)
            if definition.totalSubtasks > numFrames:
                est = int(math.floor(float(definition.totalSubtasks) / float(numFrames))) * numFrames
                if est != definition.totalSubtasks:
                    logger.warning("Too many subtasks for this task. {} subtasks will be used".format(est))
                return est

            est = int (math.ceil(float(numFrames) / float(math.ceil(float(numFrames) / float(definition.totalSubtasks)))))
            if est != definition.totalSubtasks:
                logger.warning("Too many subtasks for this task. {} subtasks will be used.".format(est))

            return est

        if renderer.defaults.minSubtasks <= definition.totalSubtasks <= renderer.defaults.maxSubtasks:
            return definition.totalSubtasks
        else :
            return renderer.defaults.defaultSubtasks

##############################################
class FrameRenderingTask(RenderingTask):
    #######################
    def __init__(self, client_id, task_id, owner_address, owner_port, ownerKeyId, environment, ttl,
                  subtaskTtl, mainProgramFile, taskResources, mainSceneDir, mainSceneFile,
                  totalTasks, resX, resY, outfilebasename, output_file, outputFormat, root_path,
                  estimated_memory, useFrames, frames):
        RenderingTask.__init__(self, client_id, task_id, owner_address, owner_port, ownerKeyId, environment, ttl,
                  subtaskTtl, mainProgramFile, taskResources, mainSceneDir, mainSceneFile,
                  totalTasks, resX, resY, outfilebasename, output_file, outputFormat, root_path,
                  estimated_memory)

        self.useFrames = useFrames
        self.frames = frames

        if useFrames:
            self.previewFilePath = [ None ] * len (frames)
            self.previewTaskFilePath = [ None ] * len(frames)

    #######################
    def restart(self):
        RenderingTask.restart(self)
        if self.useFrames:
            self.previewFilePath = [ None ] * len (self.frames)
            self.previewTaskFilePath = [ None ] * len (self.frames)

    #######################
    def _updateFramePreview(self, newChunkFilePath, frameNum, part = 1, final = False):
        num = self.frames.index(frameNum)
        if newChunkFilePath.endswith(".exr") or newChunkFilePath.endswith(".EXR"):
            img = exr_to_pil(newChunkFilePath)
        else:
            img = Image.open(newChunkFilePath)

        tmpDir = getTmpPath(self.header.client_id, self.header.task_id, self.root_path)
        if self.previewFilePath[ num ] is None:
            self.previewFilePath[ num ] = "{}{}".format(os.path.join(tmpDir, "current_preview"), num)
        if self.previewTaskFilePath[ num ] is None:
            self.previewTaskFilePath[ num ] = "{}{}".format(os.path.join(tmpDir, "current_task_preview") , num)

        if not final:
            img = self._pasteNewChunk(img, self.previewFilePath[ num ], part, self.totalTasks / len(self.frames))

        img.save(self.previewFilePath[ num ], "BMP")
        img.save(self.previewTaskFilePath[ num ], "BMP")


    #######################
    def _pasteNewChunk(self, imgChunk, previewFilePath, chunkNum, allChunksNum ):
        imgOffset = Image.new("RGB", (self.resX, self.resY))
        try:
            offset = int (math.floor((chunkNum - 1) * float(self.resY) / float(allChunksNum)))
            imgOffset.paste(imgChunk, (0, offset))
        except Exception, err:
            logger.error("Can't generate preview {}".format(str(err)))
        if os.path.exists(previewFilePath):
            img = Image.open(previewFilePath)
            img = ImageChops.add(img, imgOffset)
            return img
        else:
            return imgOffset


    #######################
    def _updateFrameTaskPreview(self):
        sentColor = (0, 255, 0)
        failedColor = (255, 0, 0)

        for sub in self.subTasksGiven.values():
            if sub['status'] == SubtaskStatus.starting:
                for frame in sub['frames']:
                    self.__markSubFrame(sub, frame, sentColor)

            if sub['status'] == SubtaskStatus.failure:
                for frame in sub['frames']:
                    self.__markSubFrame(sub, frame, failedColor)

    #######################
    def _openFramePreview(self, previewFilePath):

        if not os.path.exists(previewFilePath):
            img = Image.new("RGB", (self.resX,self.resY))
            img.save(previewFilePath, "BMP")

        return Image.open(previewFilePath)

    #######################
    def __markSubFrame(self, sub, frame, color ):
        tmpDir = getTmpPath(self.header.client_id, self.header.task_id, self.root_path)
        idx = self.frames.index(frame)
        previewTaskFilePath = "{}{}".format(os.path.join(tmpDir, "current_task_preview") , idx)
        previewFilePath = "{}{}".format(os.path.join(tmpDir, "current_preview"), idx)
        imgTask = self._openFramePreview(previewFilePath)
        self._markTaskArea(sub, imgTask, color)
        imgTask.save(previewTaskFilePath, "BMP")
        self.previewTaskFilePath[ idx ] = previewTaskFilePath

    #######################
    def _markTaskArea(self, subtask, imgTask, color):
        if not self.useFrames:
            RenderingTask._markTaskArea(self, subtask, imgTask, color)
        elif self.__fullFrames():
            for i in range(0, self.resX):
                for j in range(0, self.resY):
                    imgTask.putpixel((i, j), color)
        else:
            parts = self.totalTasks / len(self.frames)
            upper = int(math.floor(float(self.resY) /float(parts)) * ((subtask['startTask'] - 1) % parts))
            lower = int(math.floor(float(self.resY) /float(parts)) * ((subtask['startTask'] - 1) % parts   + 1))
            for i in range(0, self.resX):
                for j in range(upper, lower):
                    imgTask.putpixel((i, j), color)

    #######################
    @checkSubtask_idWrapper
    def _getPartImgSize(self, subtask_id, advTestFile):
        if not self.useFrames or self.__fullFrames():
            return RenderingTask._getPartImgSize(self, subtask_id, advTestFile)
        else:
            startTask = self.subTasksGiven[ subtask_id ][ 'startTask' ]
            parts = self.subTasksGiven[ subtask_id ][ 'parts' ]
            numTask = self._countPart(startTask, parts)
            imgHeight = int (math.floor(float(self.resY) / float(parts)))
            return 1, (numTask - 1) * imgHeight + 1, self.resX - 1, numTask * imgHeight - 1

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
                framesList = self.subTasksGiven[ subtask_id ]['frames']
                if len(task_result) < len(framesList):
                    self._markSubtaskFailed(subtask_id)
                    if not self.useFrames:
                        self._updateTaskPreview()
                    else:
                        self._updateFrameTaskPreview()
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

            for trFile in trFiles:

                if not self.useFrames:
                    self._collectImagePart(numStart, trFile)
                elif self.totalTasks <= len(self.frames):
                    framesList = self._collectFrames(numStart, trFile, framesList, tmpDir)
                else:
                    self._collectFramePart(numStart, trFile, parts, tmpDir)

            self.numTasksReceived += numEnd - numStart + 1

        print self.numTasksReceived

        if self.numTasksReceived == self.totalTasks:
            if self.useFrames:
                self._copyFrames()
            else:
                self._putImageTogether(tmpDir)



    #######################
    def _chooseFrames(self, frames, startTask, totalTasks):
        if totalTasks <= len(frames):
            subtasksFrames = int (math.ceil(float(len(frames)) / float(totalTasks)))
            startFrame = (startTask - 1) * subtasksFrames
            endFrame = min(startTask * subtasksFrames, len(frames))
            return frames[ startFrame:endFrame ], 1
        else:
            parts = totalTasks / len(frames)
            return [ frames[(startTask - 1) / parts ] ], parts

        #######################
    def _putImageTogether(self, tmpDir):
        output_file_name = u"{}".format(self.output_file, self.outputFormat)
        self.collectedFileNames = OrderedDict(sorted(self.collectedFileNames.items()))
        if not self._useOuterTaskCollector():
            collector = RenderingTaskCollector(paste = True, width = self.resX, height = self.resY)
            for file in self.collectedFileNames.values():
                collector.addImgFile(file)
            collector.finalize().save(output_file_name, self.outputFormat)
        else:
            self._putCollectedFilesTogether (os.path.join(tmpDir, output_file_name), self.collectedFileNames.values(), "paste")

    #######################
    def _putFrameTogether(self, tmpDir, frameNum, numStart):
        output_file_name = os.path.join(tmpDir, self._getOutputName(frameNum, numStart))
        collected = self.framesGiven[ frameNum ]
        collected = OrderedDict(sorted(collected.items()))
        if not self._useOuterTaskCollector():
            collector = RenderingTaskCollector(paste = True, width = self.resX, height = self.resY)
            for file in collected.values():
                collector.addImgFile(file)
            collector.finalize().save(output_file_name, self.outputFormat)
        else:
            self._putCollectedFilesTogether(output_file_name, collected.values(), "paste")
        self.collectedFileNames[ frameNum ] = output_file_name
        self._updateFramePreview(output_file_name, frameNum, final = True)
        self._updateFrameTaskPreview()

    #######################
    def _copyFrames(self):
        outpuDir = os.path.dirname(self.output_file)
        for file in self.collectedFileNames.values():
            shutil.copy(file, os.path.join(outpuDir, os.path.basename(file)))

    #######################
    def _collectImagePart(self, numStart, trFile):
        self.collectedFileNames[ numStart ] = trFile
        self._updatePreview(trFile, numStart)
        self._updateTaskPreview()

    #######################
    def _collectFrames(self, numStart, trFile, framesList, tmpDir ):
        self.framesGiven[ framesList[0] ][0] = trFile
        self._putFrameTogether(tmpDir, framesList[0], numStart)
        return framesList[1:]

    #######################
    def _collectFramePart(self, numStart, trFile, parts, tmpDir):

        frameNum = self.frames[(numStart - 1) / parts ]
        part = self._countPart(numStart, parts)
        self.framesGiven[ frameNum ][ part ] = trFile

        self._updateFramePreview(trFile, frameNum, part)

        print "collect frame {}, part {}, collected parts {}".format(frameNum, part, self.framesGiven[frameNum])
        if len(self.framesGiven[ frameNum ]) == parts:
            self._putFrameTogether(tmpDir, frameNum, numStart)


    #######################
    def __fullFrames(self):
        return self.totalTasks <= len(self.frames)

    #######################
    def _countPart(self, startNum, parts):
        return ((startNum - 1) % parts) + 1

##############################################
def get_taskBoarder(startTask, endTask, totalTasks, resX = 300, resY = 200, useFrames = False, frames = 100, frameNum = 1):
    if not useFrames:
        boarder = __getBoarder(startTask, endTask, totalTasks, resX, resY)
    elif totalTasks > frames:
        parts = totalTasks / frames
        boarder = __getBoarder((startTask - 1) % parts + 1, (endTask - 1) % parts + 1, parts, resX, resY)
    else:
        boarder = []

    return boarder

##############################################
def get_taskNumFromPixels(pX, pY, totalTasks, resX = 300, resY = 200, useFrames = False, frames = 100, frameNum = 1):
    if not useFrames:
        num = __numFromPixel(pY, resY, totalTasks)
    else:
        if totalTasks <= frames:
            subtaskFrames = int (math.ceil(float(frames)  / float(totalTasks)))
            num = int (math.ceil(float(frameNum) / subtaskFrames))
        else:
            parts = totalTasks / frames
            num = (frameNum - 1) * parts +  __numFromPixel(pY, resY, parts)
    return num

##############################################
def __getBoarder(startTask, endTask, parts, resX, resY):
    boarder = []
    upper = int(math.floor(float(resY) / float(parts)   * (startTask - 1)))
    lower = int(math.floor(float(resY) / float(parts)  * endTask ))
    for i in range(upper, lower):
        boarder.append((0, i))
        boarder.append((resX, i))
    for i in range(0,  resX):
        boarder.append((i, upper))
        boarder.append((i, lower))
    return boarder

##############################################
def __numFromPixel(pY, resY, tasks):
    return int(math.floor(pY / math.floor(float(resY) / float(tasks)))) + 1
