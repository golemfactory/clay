import os
import sys
import glob
import cPickle as pickle
import zlib
import zipfile
import subprocess
import win32process
import math

def formatVRayCmd( cmdFile, startTask, endTask, totalTasks, outputFile, outfilebasename, scenefile, width, height, rtEngine ):
    upper = int( math.floor( (startTask - 1) * ( float( height ) / float( totalTasks ) ) ) )
    lower = int( math.floor( startTask * ( float( height ) / float( totalTasks ) ) ) )
    cmd = '"{}" -imgFile="{}\\{}{}.exr" -sceneFile="{}" -imgWidth={} -imgHeight={} -region={};{};{};{} -autoClose=1 -display=0 -rtEngine={}'.format(cmdFile, outputFile, outfilebasename, startTask, scenefile, width, height, 0, upper, width, lower, rtEngine )
    return cmd

def formatVRayCmdWithFrames( cmdFile, frames, outputFile, outfilebasename, scenefile, width, height, rtEngine ):
    cmd = '"{}" -imgFile="{}\\{}.exr" -sceneFile="{}" -imgWidth={} -imgHeight={} -frames={} -region={};{};{};{} -autoClose=1 -display=0 -rtEngine={}'.format(cmdFile, outputFile, outfilebasename, scenefile, width, height, frames, 0, 0, width, height, rtEngine )
    return cmd

def formatVRayCmdWithParts( cmdFile, frames, parts, startTask, outputFile, outfilebasename, scenefile, width, height, rtEngine ):
    part = ( ( startTask - 1 ) % parts ) + 1
    upper = int( math.floor( (part  - 1) * ( float( height ) / float( parts ) ) ) )
    lower = int( math.floor( part * ( float( height ) / float( parts ) ) ) )
    cmd = '"{}" -imgFile="{}\\{}.{}.exr" -sceneFile="{}" -imgWidth={} -imgHeight={} -frames={} -region={};{};{};{}  -autoClose=1 -display=0 -rtEngine={}'.format(cmdFile, outputFile, outfilebasename, part, scenefile, width, height, frames, 0, upper, width, lower, rtEngine )
    return cmd

def __readFromEnvironment( ):
    GOLEM_ENV = 'GOLEM'
    path = os.environ.get( GOLEM_ENV )
    if not path:
        print "No Golem environment variable found... Assuming that exec is in working folder"
        return 'vray.exe'

    sys.path.append( path )

    from examples.gnr.RenderingEnvironment import VRayEnvironment
    env = VRayEnvironment()
    cmdFile = env.getCmdPath()
    if cmdFile:
        return cmdFile
    else:
        print "Environment not supported... Assuming that exec is in working folder"
        return 'vray.exe'

def outputNumber( num ):
    num = str( num )
    return num.zfill( 4 )

############################
def runVRayTask( pathRoot, startTask, endTask, totalTasks, outfilebasename, sceneFile, width, height, rtEngine, useFrames, frames, parts):
    print 'runVray Taskk'
    print frames

    outputFiles = tmpPath

    files = glob.glob( outputFiles + "*.exr" )

    for f in files:
        os.remove(f)

    print "sceneFile " + sceneFile
    if os.path.splitext( sceneFile )[1] == '.zip':
        with zipfile.ZipFile( sceneFile , "r" ) as z:
            z.extractall( os.getcwd() )
        sceneFile = glob.glob( "*.vrscene" )[0]


    cmdFile = __readFromEnvironment( )
    print "cmdFile " + cmdFile
    if os.path.exists( sceneFile ):
        if useFrames:
            frames = parseFrames ( frames )
            if parts == 1:
                if len( frames ) == 1:
                    outfilebasename = "{}.{}".format(outfilebasename, outputNumber( frames[0] ) )
                cmd = formatVRayCmdWithFrames( cmdFile, frames, outputFiles, outfilebasename, sceneFile, width, height, rtEngine )
            else:
                outfilebasename = "{}.{}".format(outfilebasename, outputNumber( frames[0] ) )
                cmd = formatVRayCmdWithParts( cmdFile, frames, parts, startTask, outputFiles, outfilebasename, sceneFile, width, height, rtEngine )
        else:
            cmd = formatVRayCmd( cmdFile, startTask, endTask, totalTasks, outputFiles,outfilebasename,  sceneFile, width, height, rtEngine )
    else:
        print "Scene file does not exist"
        return []

    print cmd

    pc = subprocess.Popen( cmd )

    win32process.SetPriorityClass( pc._handle, win32process.IDLE_PRIORITY_CLASS )


    pc.wait()

    files = glob.glob( outputFiles + "\*.exr" )

    res = []

    for f in files:
        fh = open( f, "rb" )
        fileData = fh.read()
        fileData = zlib.compress( fileData, 9 )
        res.append( pickle.dumps( ( os.path.basename( f ), fileData ) ) )
        fh.close()

    return res

def parseFrames( frames ):
    return ";".join( [ u"{}".format(frame) for frame in frames ] )

output = runVRayTask ( pathRoot, startTask, endTask, totalTasks, outfilebasename, sceneFile, width, height, rtEngine, useFrames, frames, parts )
