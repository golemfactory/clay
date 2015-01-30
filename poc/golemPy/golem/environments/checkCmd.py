import os 
import platform
import subprocess

def checkCmd( cmd ):
    prefCmd = "where" if platform.system() == "Windows" else "which"
    try:
        rc = subprocess.call([prefCmd, cmd])
        if rc == 0:
            return True
        else:
            return False
    except:
        return False
