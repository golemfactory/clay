import os
import glob
import cPickle as pickle
import zlib
import subprocess
import platform, psutil
import tempfile
import shutil
import sys

############################
def format_pbrt_cmd(renderer, startTask, endTask, totalTasks, numSubtasks, num_cores, outfilebasename, scenefile):
    return ["{}".format(renderer), "--starttask", "{}".format(startTask), "--endtask", "{}".format(endTask),
            "--outresultbasename", "{}".format(outfilebasename),  "--totaltasks",  "{}".format(totalTasks),
            "--ncores", "{}".format(num_cores), "--subtasks", "{}".format(numSubtasks), "{}".format(scenefile)]

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

def makeTmpFile(sceneDir, sceneSrc):
    if is_windows():
        tmpSceneFile = tempfile.TemporaryFile(suffix = ".pbrt", dir = sceneDir)
        tmpSceneFile.close()
        f = open(tmpSceneFile.name, 'w')
        f.write(sceneSrc)
        f.close()

        return tmpSceneFile.name
    else:
        tmpSceneFile = os.path.join(sceneDir, "tmpSceneFile.pbrt")
        f = open(tmpSceneFile, "w")
        f.write(sceneSrc)
        f.close()
        return tmpSceneFile


############################f = 
def run_pbrt_task(pathRoot, startTask, endTask, totalTasks, numSubtasks, num_cores, outfilebasename, sceneSrc, sceneDir, pbrtPath):
    pbrt = pbrtPath

    output_files = os.path.join(tmp_path, outfilebasename)

    files = glob.glob(output_files + "*.exr")

    for f in files:
        os.remove(f)


    tmpSceneFile = makeTmpFile(sceneDir, sceneSrc)

    if os.path.exists(tmpSceneFile):
        cmd = format_pbrt_cmd(pbrt, startTask, endTask, totalTasks, numSubtasks, num_cores, output_files, tmpSceneFile)
    else:
        print "Scene file does not exist"
        return {'data': [], 'result_type': 0 }
        
    print cmd
    prevDir = os.getcwd()
    os.chdir(sceneDir)

    exec_cmd(cmd)

    os.chdir(prevDir)

    print output_files

    files = glob.glob(output_files + "*.exr")

    return returnData(files)


output = run_pbrt_task(pathRoot, startTask, endTask, totalTasks, numSubtasks, num_cores, outfilebasename, sceneFileSrc, sceneDir, pbrtPath)
        