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
            file_data = fh.read()
        file_data = zlib.compress(file_data, 9)
        res.append(pickle.dumps((os.path.basename(f), file_data)))

    return { 'data': res, 'result_type': 0 }

############################
def returnFiles(files):
    copyPath = os.path.normpath(os.path.join(tmp_path, ".."))
    for f in files:
        shutil.copy2(f, copyPath)

    files = [ os.path.normpath(os.path.join(copyPath, os.path.basename(f))) for f in files]
    return {'data': files, 'result_type': 1 }

############################
def getFiles():
    output_files = tmp_path
    return glob.glob(output_files + "/*.exr")

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
def formatBlenderRenderCmd(cmdFile, output_files, outfilebasename, scene_file, scriptFile, start_task, engine, frame):
    cmd = ["{}".format(cmdFile), "-b", "{}".format(scene_file), "-P", "{}".format(scriptFile),
           "-o", "{}\{}{}".format(output_files, outfilebasename, start_task), "-E", "{}".format(engine), "-F", "EXR",
           "-f", "{}".format(frame) ]
    return cmd

############################
def runBlenderTask(outfilebasename, scene_file, scriptSrc, start_task, engine, frames):
    print "Blender Render Task"

    output_files = tmp_path

    removeOldFiles()

    sceneDir = os.path.dirname(scene_file)
    scriptFile = tempfile.TemporaryFile(suffix = ".py", dir = sceneDir)
    scriptFile.close()
    with open(scriptFile.name, 'w') as f:
        f.write(scriptSrc)

    cmdFile = __readFromEnvironment()
    scene_file = os.path.normpath(os.path.join(os.getcwd(), scene_file))
    if not os.path.exists(os.path.normpath(scene_file)):
        print "Scene file does not exist"
        return { 'data': [], 'result_type': 0 }


    for frame in frames:
        cmd = formatBlenderRenderCmd(cmdFile, output_files, outfilebasename, scene_file, scriptFile.name, start_task, engine, frame)
        print cmd
        exec_cmd(cmd)

    return returnFiles(getFiles())

output = runBlenderTask(outfilebasename, scene_file, scriptSrc, start_task, engine, frames)