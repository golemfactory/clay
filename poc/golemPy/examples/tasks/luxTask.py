import tempfile
import os
import sys
import glob
import cPickle as pickle
import zlib
import zipfile
import subprocess
import win32process
import math

def formatLuxRendererCmd( cmdFile, startTask, outputFile, outfilebasename, scenefile ):
    print "cmdFile {}".format( cmdFile )
    print "starTask {}".format( startTask )
    print "outputFile {}".format( outputFile )
    print "outfilebasename {}".format( outfilebasename )
    print "scenefile {}".format( scenefile )
    cmd = '"{}" {} -o "{}\{}{}.exr"'.format(cmdFile, scenefile, outputFile, outfilebasename, startTask )
    return cmd

def __readFromEnvironment( ):
    GOLEM_ENV = 'GOLEM'
    path = os.environ.get( GOLEM_ENV )
    if not path:
        print "No Golem environment variable found... Assuming that exec is in working folder"
        return 'luxconsole.exe'

    sys.path.append( path )

    from examples.gnr.RenderingEnvironment import LuxRenderEnvironment
    env = LuxRenderEnvironment()
    cmdFile = env.getLuxConsole()
    if cmdFile:
        return cmdFile
    else:
        print "Environment not supported... Assuming that exec is in working folder"
        return 'luxconsole.exe'

############################
def runLuxRendererTask( startTask, outfilebasename, sceneFileSrc, sceneDir ):
    print 'LuxRenderer Task'

    outputFiles = tmpPath
    print "outputFiles " + str( outputFiles )

    files = glob.glob( outputFiles + "\*.exr" ) + glob.glob( outputFiles + "\*.flm" )

    for f in files:
        os.remove(f)

    tmpSceneFile = tempfile.TemporaryFile( suffix = ".lxs", dir = sceneDir )
    tmpSceneFile.close()
    print sceneFileSrc
    f = open(tmpSceneFile.name, 'w')
    f.write( sceneFileSrc )
    f.close()

    cmdFile = __readFromEnvironment( )
    print "cmdFile " + cmdFile
    if os.path.exists( tmpSceneFile.name ):
        print tmpSceneFile.name
        cmd = formatLuxRendererCmd( cmdFile, startTask, outputFiles, outfilebasename, tmpSceneFile.name )
    else:
         print "Scene file does not exist"
         return []

    print cmd
    prevDir = os.getcwd()
    os.chdir( sceneDir )

    pc = subprocess.Popen( cmd )
    win32process.SetPriorityClass( pc._handle, win32process.IDLE_PRIORITY_CLASS )
    pc.wait()
    os.chdir( prevDir )
    files = glob.glob( outputFiles + "\*.exr" ) + glob.glob( outputFiles + "\*.flm" )

    res = []

    for f in files:
        fh = open( f, "rb" )
        fileData = fh.read()
        fileData = zlib.compress( fileData, 9 )
        res.append( pickle.dumps( ( os.path.basename( f ), fileData ) ) )
        fh.close()

    return res

output = runLuxRendererTask ( startTask, outfilebasename, sceneFileSrc, sceneDir )
