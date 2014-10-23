import os
import stat
import glob
import cPickle as pickle
import zlib
import subprocess
import shutil
import platform, psutil
import win32api, win32process
import tempfile


def format3dsMaxCmd( dsmaxcmd, startTask, endTask, totalTasks, numSubtaks, numCores, outfilebasename, scenefile, width, height, presetFile ):
    cmd = '{} -outputName:{}\\chunk{}.exr -strip:{},0,{} {} -rfw:0 -width={} -height={} -rps:"{}"'.format(dsmaxcmd, outfilebasename, startTask, totalTasks, startTask, scenefile, width, height, presetFile )
    print cmd
    return cmd

############################f =
def run3dsMaxTask( pathRoot, startTask, endTask, totalTasks, numSubtasks, numCores, outfilebasename, sceneSrc, sceneFile, width, height, preset ):
    print 'run3dsMaxTask'
    dsmaxpath = os.environ.get('ADSK_3DSMAX_x64_2015')
    dsmaxcmd = os.path.join( dsmaxpath, '3dsmaxcmd.exe')

    print dsmaxpath
    print dsmaxcmd
    outputFiles = tmpPath

    files = glob.glob( outputFiles + "*.exr" )

    for f in files:
        os.remove(f)

    sceneFile = os.path.join( resourcePath, sceneFile )

    if preset:
        print preset
        presetFile = os.path.join( resourcePath, preset)
    else:
        presetFile = os.path.join( dsmaxpath,  'renderpresets\mental.ray.daylighting.high.rps')


    if os.path.exists( sceneFile ):
        cmd = format3dsMaxCmd( dsmaxcmd, startTask, endTask, totalTasks, numSubtasks, numCores, outputFiles, sceneFile, width, height, presetFile )
    else:
        print "Scene file does not exist"

    print cmd

    pc = subprocess.Popen( cmd )

    win32process.SetPriorityClass( pc._handle, win32process.IDLE_PRIORITY_CLASS )

    pc.wait()

    print outputFiles
    print outputFiles + "\*.exr"

    files = glob.glob( outputFiles + "\*.exr" )

    print files

    res = []

    for f in files:
        fh = open( f, "rb" )
        fileData = fh.read()
        fileData = zlib.compress( fileData, 9 )
        res.append( pickle.dumps( ( os.path.basename( f ), fileData ) ) )
        fh.close()

    return res


output = run3dsMaxTask ( pathRoot, startTask, endTask, totalTasks, numSubtasks, numCores, outfilebasename, sceneFileSrc, sceneFile, width, height, presetFile )
