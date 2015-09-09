import os
import sys
import glob
import cPickle as pickle
import zlib
import zipfile
import subprocess
import win32process
import shutil

def format3dsMaxCmd(cmdFile, start_task, end_task, total_tasks, output_file, outfilebasename, scenefile, width, height, presetFile, overlap):
    cmd = '{} -outputName:{}\\{}.exr -strip:{},{},{} "{}" -frames:0 -stillFrame -rfw:0 -width={} -height={} -rps:"{}"'.format(cmdFile,output_file,  outfilebasename, total_tasks, overlap, start_task, scenefile, width, height, presetFile)
    return cmd

def format3dsMaxCmdWithFrames(cmdFile, frames, output_file, outfilebasename, scenefile, width, height, presetFile):
    cmd = '{} -outputName:{}\\{}.exr -frames:{} "{}" -rfw:0 -width={} -height={} -rps:"{}"'.format(cmdFile, output_file, outfilebasename, frames, scenefile, width, height, presetFile)
    return cmd

def format3dsMaxCmdWithParts(cmdFile, frames, parts, start_task, output_file, outfilebasename, scene_file, width, height, presetFile, overlap):
    part = ((start_task - 1) % parts) + 1
    cmd = '{} -outputName:{}\\{}.exr -frames:{} -strip:{},{},{} "{}" -rfw:0 -width={} -height={} -rps:"{}"'.format(cmdFile, output_file, outfilebasename, frames, parts, overlap, part, scene_file, width, height, presetFile)
    return cmd

def __readFromEnvironment(defaultCmdFile, num_cores):
    GOLEM_ENV = 'GOLEM'
    path = os.environ.get(GOLEM_ENV)
    if not path:
        print "No Golem environment variable found... Assuming that exec is in working folder"
        return defaultCmdFile

    sys.path.append(path)

    from examples.gnr.RenderingEnvironment import ThreeDSMaxEnvironment
    env = ThreeDSMaxEnvironment()
    cmdFile = env.get3dsmaxcmdPath()
    if cmdFile:
    #    env.setNThreads(num_cores)
        return cmdFile
    else:
        print "Environment not supported... Assuming that exec is in working folder"
        return defaultCmdFile

###########################
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



############################f =
def run3dsMaxTask(path_root, start_task, end_task, total_tasks, outfilebasename, scene_file, width, height, preset, cmdFile, useFrames, frames, parts, num_cores, overlap):
    print 'run3dsMaxTask'
    output_files = tmp_path

    files = glob.glob(output_files + "*.exr")

    for f in files:
        os.remove(f)

    if os.path.splitext(scene_file)[1] == '.zip':
        with zipfile.ZipFile(scene_file , "r", allowZip64 = True) as z:
            z.extractall(os.getcwd())
        scene_file = glob.glob("*.max")[0]

    if preset:
        presetFile = os.path.normpath( os.path.join(os.getcwd(), preset))
    else:
        presetFile = os.path.join(dsmaxpath,  'renderpresets\mental.ray.daylighting.high.rps')


    cmdFile = __readFromEnvironment(cmdFile, num_cores)
    if os.path.exists(scene_file):
        if useFrames:
            frames = parseFrames(frames)
            if parts == 1:
                cmd = format3dsMaxCmdWithFrames(cmdFile, frames, output_files, outfilebasename, scene_file, width, height, presetFile)
            else:
                cmd = format3dsMaxCmdWithParts(cmdFile, frames, parts, start_task, output_files, outfilebasename, scene_file, width, height, presetFile, overlap)
        else:
            cmd = format3dsMaxCmd(cmdFile, start_task, end_task, total_tasks, output_files, outfilebasename, scene_file, width, height, presetFile, overlap)

    else:
        print "Scene file does not exist"
        return {'data': [], 'result_type': 0 }

    print cmd

    pc = subprocess.Popen(cmd)

    win32process.SetPriorityClass(pc._handle, win32process.IDLE_PRIORITY_CLASS)


    pc.wait()

    files = glob.glob(output_files + "\*.exr")

    return returnData(files)

def parseFrames(frames):
    return ",".join([ u"{}".format(frame) for frame in frames ])

output = run3dsMaxTask (path_root, start_task, end_task, total_tasks, outfilebasename, scene_file, width, height, presetFile, cmdFile, useFrames, frames, parts, num_cores, overlap)
