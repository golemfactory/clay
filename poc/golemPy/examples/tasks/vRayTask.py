import os
import sys
import glob
import cPickle as pickle
import zlib
import zipfile
import subprocess
import psutil
import math
import shutil

def formatTestVRayCmd(cmdFile, output_file, outfilebasename, scenefile, width, height, rtEngine, numThreads):
    cmd = ["{}".format(cmdFile), "-imgFile={}/{}.exr".format(output_file, outfilebasename),
           "-sceneFile={}".format(scenefile), "-imgWidth={}".format(width), "-imgHeight={}".format(height),
           "-region={};{};{};{}".format(startBox[0], startBox[1], startBox[0] + box[0], startBox[1] + box[1]),
           "-autoClose=1", "-display=0", "-rtEngine={}".format(rtEngine), "-numThreads={}".format(numThreads) ]
    return cmd

def formatTestVRayCmdWithParts(cmdFile, frames,  output_file, outfilebasename, scenefile, width, height, rtEngine, numThreads):
    cmd = ["{}".format(cmdFile), "-imgFile={}/{}.exr".format(output_file, outfilebasename),
           "-sceneFile={}".format(scenefile), "-imgWidth={}".format(width), "-imgHeight={}".format(height),
           "-frames={}".format(frames), "-region={};{};{};{}".format(0, startBox[1], width, startBox[1] + box[1]),
           "-autoClose=1", "-display=0", "-rtEngine={}".format(rtEngine), "-numThreads={}".format(numThreads) ]
    return cmd

def formatVRayCmd(cmdFile, startTask, endTask, hTasks, totalTasks, output_file, outfilebasename, scenefile, width, height, rtEngine, numThreads):
    if 'generateStartBox' in globals():
        return formatTestVRayCmd(cmdFile, output_file, outfilebasename, scenefile, width, height, rtEngine, numThreads)
    wTasks = totalTasks / hTasks
    partWidth = width / wTasks
    partHeight = height / hTasks
    left = ((int(startTask) - 1) / int(hTasks)) * partWidth
    right = left + partWidth
    upper = ((startTask - 1) % hTasks) * partHeight
    lower = upper + partHeight
    cmd = ["{}".format(cmdFile), "-imgFile={}/{}{}.exr".format(output_file, outfilebasename, startTask),
           "-sceneFile={}".format(scenefile), "-imgWidth={}".format(width),  "-imgHeight={}".format(height),
           "-region={};{};{};{}".format(left, upper, right, lower), "-autoClose=1", "-display=0",
           "-rtEngine={}".format(rtEngine), "-numThreads={}".format(numThreads) ]
    return cmd

def formatVRayCmdWithFrames(cmdFile, frames, output_file, outfilebasename, scenefile, width, height, rtEngine, numThreads):
    cmd = ["{}".format(cmdFile), "-imgFile={}/{}.exr".format(output_file, outfilebasename),
           "-sceneFile={}".format(scenefile), "-imgWidth={}".format(width), "-imgHeight={}".format(height),
           "-frames={}".format(frames), "-region={};{};{};{}".format(0, 0, width, height),
           "-autoClose=1", "-display=0", "-rtEngine={}".format(rtEngine), "-numThreads={}".format(numThreads) ]
    return cmd

def formatVRayCmdWithParts(cmdFile, frames, parts, startTask, output_file, outfilebasename, scenefile, width, height, rtEngine, numThreads):
    if 'generateStartBox' in globals():
        return formatTestVRayCmdWithParts(cmdFile, frames, output_file, outfilebasename, scenefile, width, height, rtEngine, numThreads)
    part = ((startTask - 1) % parts) + 1
    upper = int(math.floor((part  - 1) * (float(height) / float(parts))))
    lower = int(math.floor(part * (float(height) / float(parts))))
    cmd = ["{}".format(cmdFile), "-imgFile={}/{}.{}.exr".format(output_file, outfilebasename, part),
           "-sceneFile={}".format(scenefile), "-imgWidth={}".format(width), "-imgHeight={}".format(height),
           "-frames={}".format(frames), "-region={};{};{};{}".format(0, upper, width, lower),
           "-autoClose=1", "-display=0", "-rtEngine={}".format(rtEngine),  "-numThreads={}".format(numThreads)]
    return cmd

def __readFromEnvironment():
    GOLEM_ENV = 'GOLEM'
    path = os.environ.get(GOLEM_ENV)
    if not path:
        print "No Golem environment variable found... Assuming that exec is in working folder"
        if is_windows():
            return 'vray.exe'
        else:
            return 'vray'

    sys.path.append(path)

    from examples.gnr.RenderingEnvironment import VRayEnvironment
    env = VRayEnvironment()
    cmdFile = env.getCmdPath()
    if cmdFile:
        return cmdFile
    else:
        print "Environment not supported... Assuming that exec is in working folder"
        if is_windows():
            return 'vray.exe'
        else:
            return 'vray'

def outputNumber(num):
    num = str(num)
    return num.zfill(4)


############################
def returnData(files):
    res = []
    for f in files:
        with open(f, "rb") as fh:
            file_data = fh.read()
        file_data = zlib.compress(file_data, 9)
        res.append(pickle.dumps((os.path.basename(f), file_data)))

    return { 'data': res, 'result_type': 0 }

############################
def is_windows():
    return sys.platform == 'win32'

def exec_cmd(cmd, nice=20):
    pc = subprocess.Popen(cmd)
    if is_windows():
        import win32process
        win32process.SetPriorityClass(pc._handle, win32process.IDLE_PRIORITY_CLASS)
    else:
        p = psutil.Process(pc.pid)
        p.nice(nice)

    pc.wait()

############################
def returnFiles(files):
    copyPath = os.path.normpath(os.path.join(tmp_path, ".."))
    for f in files:
        shutil.copy2(f, copyPath)

    files = [ os.path.normpath(os.path.join(copyPath, os.path.basename(f))) for f in files]
    return {'data': files, 'result_type': 1 }

############################
def runVRayTask(pathRoot, startTask, endTask, hTask, totalTasks, outfilebasename, sceneFile, width, height, rtEngine, useFrames, frames, parts, numThreads):
    print 'runVray Taskk'
    print frames

    output_files = tmp_path

    files = glob.glob(output_files + "/*.exr")

    for f in files:
        os.remove(f)

    print "sceneFile " + sceneFile
    if os.path.splitext(sceneFile)[1] == '.zip':
        with zipfile.ZipFile(sceneFile , "r", allowZip64 = True) as z:
            z.extractall(os.getcwd())
        sceneFile = glob.glob("*.vrscene")[0]


    cmdFile = __readFromEnvironment()
    print "cmdFile " + cmdFile
    if os.path.exists(sceneFile):
        if useFrames:
            frames = parseFrames (frames)
            if parts == 1:
                if len(frames) == 1:
                    outfilebasename = "{}.{}".format(outfilebasename, outputNumber(frames[0]))
                cmd = formatVRayCmdWithFrames(cmdFile, frames, output_files, outfilebasename, sceneFile, width, height, rtEngine, numThreads)
            else:
                outfilebasename = "{}.{}".format(outfilebasename, outputNumber(frames[0]))
                cmd = formatVRayCmdWithParts(cmdFile, frames, parts, startTask, output_files, outfilebasename, sceneFile, width, height, rtEngine, numThreads)
        else:
            cmd = formatVRayCmd(cmdFile, startTask, endTask, hTask, totalTasks, output_files,outfilebasename,  sceneFile, width, height, rtEngine, numThreads)
    else:
        print "Scene file does not exist"
        return {'data': [], 'result_type': 0 }

    print cmd

    exec_cmd(cmd)

    files = glob.glob(output_files + "/*.exr")

    return returnData(files)

def parseFrames(frames):
    return ";".join([ u"{}".format(frame) for frame in frames ])

output = runVRayTask (pathRoot, startTask, endTask, hTask, totalTasks, outfilebasename, sceneFile, width, height, rtEngine, useFrames, frames, parts, numThreads)
