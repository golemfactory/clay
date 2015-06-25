import tempfile
import os
import sys
import glob
import cPickle as pickle
import zlib
import subprocess
import shutil
import psutil

############################
def returnData(files):
    res = []
    for f in files:
        with open(f, "rb") as fh:
            fileData = fh.read()
        fileData = zlib.compress(fileData, 9)
        res.append(pickle.dumps((os.path.basename(f), fileData)))

    return { 'data': res, 'resultType': 0 }

############################
def returnFiles(files):
    copyPath = os.path.normpath(os.path.join(tmpPath, ".."))
    for f in files:
        shutil.copy2(f, copyPath)

    files = [ os.path.normpath(os.path.join(copyPath, os.path.basename(f))) for f in files]
    return {'data': files, 'resultType': 1 }

############################
def getFiles():
    outputFiles = tmpPath
    return glob.glob(outputFiles + "/*.exr")

############################
def removeOldFiles():
    for f in getFiles():
        os.remove(f)

def __readFromEnvironment():
    defaultCmdFile = 'blender'
    GOLEM_ENV = 'GOLEM'
    path = os.environ.get(GOLEM_ENV)
    if not path:
        print "No Golem environment variable found..."
        return defaultCmdFile

    sys.path.append(path)

    from examples.gnr.RenderingEnvironment import BlenderEnvironment
    env = BlenderEnvironment()
    cmdFile = env.getBlender()
    if cmdFile:
        return cmdFile
    else:
        return defaultCmdFile

############################
def isWindows():
    return sys.platform == 'win32'

def execCmd(cmd, nice = 20):
    pc = subprocess.Popen(cmd)
    if isWindows():
        import win32process
        win32process.SetPriorityClass(pc._handle, win32process.IDLE_PRIORITY_CLASS)
    else:
        p = psutil.Process(pc.pid)
        p.set_nice(nice)

    pc.wait()

############################
def formatBlenderRenderCmd(cmdFile, outputFiles, outfilebasename, sceneFile, scriptFile, startTask, engine, frame):
    cmd = ["{}".format(cmdFile), "-b", "{}".format(sceneFile), "-P", "{}".format(scriptFile),
           "-o", "{}\{}{}".format(outputFiles, outfilebasename, startTask), "-E", "{}".format(engine), "-F", "EXR",
           "-f", "{}".format(frame) ]
    return cmd

############################
def runBlenderTask(outfilebasename, sceneFile, scriptSrc, startTask, engine, frames):
    print "Blender Render Task"

    outputFiles = tmpPath

    removeOldFiles()

    sceneDir = os.path.dirname(sceneFile)
    scriptFile = tempfile.TemporaryFile(suffix = ".py", dir = sceneDir)
    scriptFile.close()
    with open(scriptFile.name, 'w') as f:
        f.write(scriptSrc)

    cmdFile = __readFromEnvironment()
    sceneFile = os.path.normpath(os.path.join(os.getcwd(), sceneFile))
    if not os.path.exists(os.path.normpath(sceneFile)):
        print "Scene file does not exist"
        return { 'data': [], 'resultType': 0 }


    for frame in frames:
        cmd = formatBlenderRenderCmd(cmdFile, outputFiles, outfilebasename, sceneFile, scriptFile.name, startTask, engine, frame)
        print cmd
        execCmd(cmd)

    return returnFiles(getFiles())

output = runBlenderTask(outfilebasename, sceneFile, scriptSrc, startTask, engine, frames)