import os 
import platform
import subprocess

def checkCmd( cmd, noOutput = True ):
    prefCmd = "where" if platform.system() == "Windows" else "which"
    try:
        if noOutput:
            rc = subprocess.check_output( [prefCmd, cmd], stderr=subprocess.STDOUT )
            return True
        else:
            rc = subprocess.call([prefCmd, cmd])
            return rc == 0
    except Exception, err:
        return False
