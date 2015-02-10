import tempfile
import os
import sys
import glob
import cPickle as pickle
import zlib
import subprocess
import win32process
import shutil

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
def getFiles():
    outputFiles = tmpPath
    return glob.glob( outputFiles + "\*.exr" )

############################
def removeOldFiles():
    for f in getFiles():
        os.remove( f )

def __readFromEnvironment():
    defaultCmdFile = 'blender'
    GOLEM_ENV = 'GOLEM'
    path = os.environ.get( GOLEM_ENV )
    if not path:
        print "No Golem environment variable found..."
        return defaultCmdFile

    sys.path.append( path )

    from examples.gnr.RenderingEnvironment import BlenderEnvironment
    env = BlenderEnvironment()
    cmdFile = env.getBlender()
    if cmdFile:
        return cmdFile
    else:
        return defaultCmdFile

############################
def runCmd( cmd ):
    pc = subprocess.Popen( cmd )
    win32process.SetPriorityClass( pc._handle, win32process.IDLE_PRIORITY_CLASS )
    pc.wait()

def formatBlenderRenderCmd( cmdFile, outputFiles, outfilebasename, sceneFile, scriptFile, startTask, engine, frame ):
    cmd = '"{}" -b "{}" -P "{}" -o "{}\{}{}" -E {} -F EXR -f {} '.format( cmdFile, sceneFile, scriptFile, outputFiles, outfilebasename, startTask, engine, frame )
    return cmd

############################
def runBlenderTask( outfilebasename, sceneFile, scriptSrc, startTask, engine, frames ):
    print "Blender Render Task"

    outputFiles = tmpPath

    removeOldFiles()

    sceneDir = os.path.dirname( sceneFile )
    scriptFile = tempfile.TemporaryFile( suffix = ".py", dir = sceneDir )
    scriptFile.close()
    f = open( scriptFile.name, 'w')
    f.write( scriptSrc )
    f.close()


    cmdFile = __readFromEnvironment()
    if not os.path.exists( sceneFile ):
        print "Scene file does not exist"
        return []

    for frame in frames:
        cmd = formatBlenderRenderCmd( cmdFile, outputFiles, outfilebasename, sceneFile, scriptFile.name, startTask, engine, frame )
        print cmd
        runCmd( cmd )

    return returnFiles( getFiles() )

output = runBlenderTask( outfilebasename, sceneFile, scriptSrc, startTask, engine, frames )