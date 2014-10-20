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
    print "Inside run3dsMaxTask"
    #if not os.path.isdir( outfilebasename ):
     #   os.mkdir(outfilebasename)
    cmd = '{} -outputName:{}\\chunk{}.exr -strip:{},0,{} {} -rfw:0 -width={} -height={} -rps:"{}"'.format(dsmaxcmd, outfilebasename, startTask, totalTasks, startTask, scenefile, width, height, presetFile )
    print cmd
    return cmd

############################f =
def run3dsMaxTask( pathRoot, startTask, endTask, totalTasks, numSubtasks, numCores, outfilebasename, sceneSrc, sceneFile, width, height ):
    print 'run3dsMaxTask'
    dsmaxpath = os.environ.get('ADSK_3DSMAX_x64_2015')
    dsmaxcmd = os.path.join( dsmaxpath, '3dsmaxcmd.exe')
    presetFile = os.path.join( dsmaxpath,  'renderpresets\mental.ray.daylighting.high.rps')

    print dsmaxpath
    print dsmaxcmd
    print presetFile
   # outputFiles = os.path.join( tmpPath, outfilebasename )
    outputFiles = tmpPath

    files = glob.glob( outputFiles + "*.exr" )

    for f in files:
        os.remove(f)

    tmpSceneFile = tempfile.TemporaryFile( suffix = ".max", dir = os.path.join( resourcePath, "resources" ) )
    print tmpSceneFile.name
    tmpSceneFile.close()
    sceneFile = os.path.join( resourcePath, sceneFile )
    print sceneFile
    shutil.copyfile(sceneFile, tmpSceneFile.name)

    print tmpSceneFile.name

    if os.path.exists( tmpSceneFile.name ):
        cmd = format3dsMaxCmd( dsmaxcmd, startTask, endTask, totalTasks, numSubtasks, numCores, outputFiles, tmpSceneFile.name, width, height, presetFile )
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

   # os.remove( outfilebasename )

    return res


output = run3dsMaxTask ( pathRoot, startTask, endTask, totalTasks, numSubtasks, numCores, outfilebasename, sceneFileSrc, sceneFile,width, height )
