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
import shutil

def formatLuxRendererCmd( cmdFile, startTask, outputFile, outfilebasename, scenefile, numThreads ):
    print "cmdFile {}".format( cmdFile )
    print "starTask {}".format( startTask )
    print "outputFile {}".format( outputFile )
    print "outfilebasename {}".format( outfilebasename )
    print "scenefile {}".format( scenefile )
    cmd = '"{}" {} -o "{}\{}{}.png" -q -t {}'.format(cmdFile, scenefile, outputFile, outfilebasename, startTask, numThreads )
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
def returnData( files ):
    res = []
    for f in files:
        fh = open( f, "rb" )
        fileData = fh.read()
        fileData = zlib.compress( fileData, 9 )
        res.append( pickle.dumps( ( os.path.basename( f ), fileData ) ) )
        fh.close()

    return { 'data': res, 'resultType': 0 }

############################
def returnFiles( files ):
    copyPath = os.path.normpath( os.path.join( tmpPath, "..") )
    for f in files:
        shutil.copy2( f, copyPath )

    files = [ os.path.normpath( os.path.join( copyPath, os.path.basename( f ) ) ) for f in files]
    return {'data': files, 'resultType': 1 }


############################
def runLuxRendererTask( startTask, outfilebasename, sceneFileSrc, sceneDir, numCores, ownBinaries, luxConsole ):
    print 'LuxRenderer Task'

    outputFiles = tmpPath
    print "outputFiles " + str( outputFiles )

    files = glob.glob( outputFiles + "\*.png" ) + glob.glob( outputFiles + "\*.flm" )

    for f in files:
        os.remove(f)

    tmpSceneFile = tempfile.TemporaryFile( suffix = ".lxs", dir = sceneDir )
    tmpSceneFile.close()
    print sceneFileSrc
    f = open(tmpSceneFile.name, 'w')
    f.write( sceneFileSrc )
    f.close()

    if ownBinaries:
        cmdFile = luxConsole
    else:
        cmdFile = __readFromEnvironment( )
    print "cmdFile " + cmdFile
    if os.path.exists( tmpSceneFile.name ):
        print tmpSceneFile.name
        cmd = formatLuxRendererCmd( cmdFile, startTask, outputFiles, outfilebasename, tmpSceneFile.name, numThreads )
    else:
         print "Scene file does not exist"
         return []

    print cmd
    prevDir = os.getcwd()
    print prevDir
    os.chdir( sceneDir )
    print sceneDir

    pc = subprocess.Popen( cmd )
    win32process.SetPriorityClass( pc._handle, win32process.IDLE_PRIORITY_CLASS )
    pc.wait()
    os.chdir( prevDir )
    files = glob.glob( outputFiles + "\*.png" ) + glob.glob( outputFiles + "\*.flm" )

    return returnFiles( files )


output = runLuxRendererTask ( startTask, outfilebasename, sceneFileSrc, sceneDir, numThreads, ownBinaries, luxConsole )
