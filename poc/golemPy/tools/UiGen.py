import os

def regenerateUIFiles( rootPath ):
    
    dirs  = [ name for name in os.listdir( rootPath ) if os.path.isdir( os.path.join( rootPath, name ) ) ]
    files = [ name for name in os.listdir( rootPath ) if os.path.isfile( os.path.join( rootPath, name ) ) ]
    
    for dir in dirs:
        regenerateUIFiles( os.path.join( rootPath, dir ) )

    for file in files:
        if file.endswith( ".ui" ):
            outFile = "ui_" + file[0:-3] + ".py"

            if os.path.exists( os.path.join( rootPath, outFile ) ) and not os.path.isdir( os.path.join( rootPath, outFile ) ):
                if os.path.getmtime( os.path.join( rootPath, outFile ) ) > os.path.getmtime(  os.path.join( rootPath, file ) ):
                    continue
            print "Generating " + outFile
            os.system( "python ./../src/ui/pyuic.py " + os.path.join( rootPath, file ) + " > " + os.path.join( rootPath, outFile )  )

def genUiFiles( path ):
    if os.path.exists( path ):
        regenerateUIFiles( path )
    else:
        cwd = os.getcwd()
        assert False, "UiGen: Cannot find " + path + " dir or wrong working directory: "  + cwd
    