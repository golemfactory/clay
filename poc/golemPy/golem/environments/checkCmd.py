import os 
import platform
import subprocess

def check_cmd(cmd, no_output = True):
    pref_cmd = "where" if platform.system() == "Windows" else "which"
    try:
        if no_output:
            rc = subprocess.check_output([pref_cmd, cmd], stderr=subprocess.STDOUT)
            return True
        else:
            rc = subprocess.call([pref_cmd, cmd])
            return rc == 0
    except Exception, err:
        return False
