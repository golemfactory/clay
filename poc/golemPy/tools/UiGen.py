import os

def regenerateUIFiles( rootPath ):
    
    dirs  = [ name for name in os.listdir( rootPath ) if os.path.isdir( os.path.join( rootPath, name ) ) ]
    files = [ name for name in os.listdir( rootPath ) if os.path.isfile( os.path.join( rootPath, name ) ) ]
    pyuicPath = './../src/ui/pyuic.py'
    
    for dir in dirs:
        regenerateUIFiles( os.path.join( rootPath, dir ) )

    for file in files:
        if file.endswith( ".ui" ):
            outFile = os.path.join( "gen", "ui_" + file[0:-3] + ".py" )
            outFilePath = os.path.join( rootPath, outFile )

            if os.path.exists( outFilePath ) and not os.path.isdir( outFilePath ):
                if os.path.getmtime( outFilePath ) > os.path.getmtime(  os.path.join( rootPath, file ) ):
                    if os.path.getsize( outFilePath ) > 0:
                        continue

            assert os.path.exists(pyuicPath), "Can't open file " + pyuicPath

            print "Generating " + outFile
            os.system( "python " + pyuicPath + " " + os.path.join( rootPath, file ) + " > " + os.path.join( rootPath, outFile )  )

def genUiFiles( path ):
    if os.path.exists( path ):
        regenerateUIFiles( path )
    else:
        cwd = os.getcwd()
        assert False, "UiGen: Cannot find " + path + " dir or wrong working directory: "  + cwd
    