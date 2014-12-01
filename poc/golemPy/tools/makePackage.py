import glob
import shutil
import os
import sys
import py_compile

def makeFolder( dest ):
    if not os.path.isdir( dest ):
        os.mkdir( dest )

def copyFiles( dest, src ):
    files = glob.glob( os.path.join( src, '*.pyc') ) + glob.glob( os.path.join( src, '*.ini') )
    files += glob.glob( os.path.join( src, '*.jpg') ) + glob.glob( os.path.join( src, '*.exe') )
    files += glob.glob( os.path.join( src, '*.txt') ) + glob.glob( os.path.join( src, '*.dll' ) )
    files += glob.glob( os.path.join( src, '*.gt' ) )
    for f in files:
        shutil.copy( f, os.path.join( dest, os.path.basename( f ) ) )

def copyToPackage( dest, src ):
    copyFiles( dest, src )
    dirs  = [ name for name in os.listdir( src ) if os.path.isdir( os.path.join( src, name ) ) ]
    for d in dirs:
        destDir = os.path.join( dest, d )
        print destDir
        if not os.path.isdir( destDir ):
            os.mkdir( destDir )

        print os.path.join( src, d )
        if os.path.isdir( os.path.join( src, d ) ):
            copyToPackage( destDir ,  os.path.join(src, d ) )

def main():

    if len( sys.argv ) > 1:
        dest = sys.argv[1]
    else:
        dest = "C:\golem_test\package"

    srcPath = os.environ.get( 'GOLEM' )
    print srcPath
    py_compile.compile( os.path.join( srcPath, 'examples\\gnr\\main.py' ) )

    makeFolder( dest )
    copyToPackage( dest, srcPath)

main()