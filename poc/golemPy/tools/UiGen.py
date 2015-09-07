import os
import logging

logger = logging.getLogger(__name__)

def regenerateUIFiles(root_path):
    
    dirs  = [ name for name in os.listdir(root_path) if os.path.isdir(os.path.join(root_path, name)) ]
    files = [ name for name in os.listdir(root_path) if os.path.isfile(os.path.join(root_path, name)) ]
    pyuicPath = 'pyuic.py'
    
    for dir in dirs:
        regenerateUIFiles(os.path.join(root_path, dir))

    pth, filename =  os.path.split(os.path.realpath(__file__))
    pyuicPath = os.path.join(pth, pyuicPath)

    for file in files:
        if file.endswith(".ui"):
            outFile = os.path.join("gen", "ui_" + file[0:-3] + ".py")
            outFilePath = os.path.join(root_path, outFile)

            if os.path.exists(outFilePath) and not os.path.isdir(outFilePath):
                if os.path.getmtime(outFilePath) > os.path.getmtime( os.path.join(root_path, file)):
                    if os.path.getsize(outFilePath) > 0:
                        continue

            assert os.path.exists(pyuicPath), "Can't open file " + pyuicPath

            logger.info("Generating " + outFile)
            os.system("python " + pyuicPath + " " + os.path.join(root_path, file) + " > " + os.path.join(root_path, outFile) )

def genUiFiles(path):
    if os.path.exists(path):
        regenerateUIFiles(path)
    else:
        cwd = os.getcwd()
        assert False, "UiGen: Cannot find " + path + " dir or wrong working directory: "  + cwd
    