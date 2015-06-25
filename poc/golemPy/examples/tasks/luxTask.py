import tempfile
import os
import sys
import glob
import cPickle as pickle
import zlib
import zipfile
import subprocess
import psutil
import shutil

def formatLuxRendererCmd(cmdFile, startTask, outputFile, outfilebasename, scenefile, numThreads):
    cmd = ["{}".format(cmdFile), "{}".format(scenefile), "-o",
           "{}\{}{}.png".format(outputFile, outfilebasename, startTask), "-q", "-t", "{}".format(numThreads) ]
    print cmd
    return cmd

def __readFromEnvironment():
    GOLEM_ENV = 'GOLEM'
    path = os.environ.get(GOLEM_ENV)
    if not path:
        print "No Golem environment variable found... Assuming that exec is in working folder"
        if isWindows():
            return 'luxconsole.exe'
        else:
            return 'luxconsole'

    sys.path.append(path)

    from examples.gnr.RenderingEnvironment import LuxRenderEnvironment
    env = LuxRenderEnvironment()
    cmdFile = env.getLuxConsole()
    if cmdFile:
        return cmdFile
    else:
        print "Environment not supported... Assuming that exec is in working folder"
        if isWindows():
            return 'luxconsole.exe'
        else:
            return 'luxconsole'

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

def makeTmpFile(sceneDir, sceneSrc):
    if isWindows():
        tmpSceneFile = tempfile.TemporaryFile(suffix = ".lxs", dir = sceneDir)
        tmpSceneFile.close()
        f = open(tmpSceneFile.name, 'w')
        f.write(sceneSrc)
        f.close()

        return tmpSceneFile.name
    else:
        tmpSceneFile = os.path.join(sceneDir, "tmpSceneFile.lxs")
        f = open(tmpSceneFile, "w")
        f.write(sceneSrc)
        f.close()
        return tmpSceneFile


############################
def runLuxRendererTask(startTask, outfilebasename, sceneFileSrc, sceneDir, numCores, ownBinaries, luxConsole):
    print 'LuxRenderer Task'

    outputFiles = tmpPath
    print "outputFiles " + str(outputFiles)

    files = glob.glob(outputFiles + "/*.png") + glob.glob(outputFiles + "/*.flm")

    for f in files:
        os.remove(f)

    tmpSceneFile = makeTmpFile(sceneDir, sceneFileSrc)

    if ownBinaries:
        cmdFile = luxConsole
    else:
        cmdFile = __readFromEnvironment()
    print "cmdFile " + cmdFile
    if os.path.exists(tmpSceneFile):
        print tmpSceneFile
        cmd = formatLuxRendererCmd(cmdFile, startTask, outputFiles, outfilebasename, tmpSceneFile, numThreads)
    else:
         print "Scene file does not exist"
         return {'data': [], 'resultType': 0 }

    prevDir = os.getcwd()
    os.chdir(sceneDir)

    execCmd(cmd)

    os.chdir(prevDir)
    files = glob.glob(outputFiles + "/*.png") + glob.glob(outputFiles + "/*.flm")

    return returnFiles(files)


output = runLuxRendererTask (startTask, outfilebasename, sceneFileSrc, sceneDir, numThreads, ownBinaries, luxConsole)
