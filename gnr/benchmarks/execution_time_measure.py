import sys
import psutil
import subprocess
import time


# UGLY! is_windows and exec_cmd are copy-pasted from $GOLEM/gnr/task/scripts/luxtask.py

def is_windows():
    return sys.platform == 'win32'


def exec_cmd(cmd, nice=20):
    pc = subprocess.Popen(cmd)
    if is_windows():
        import win32process
        win32process.SetPriorityClass(pc._handle, win32process.IDLE_PRIORITY_CLASS)
    else:
        p = psutil.Process(pc.pid)
        p.nice(nice)

    pc.wait()


# -----------------------------------------------------------------------------
def measure(command):
    '''
    returns time of execution of the command (in seconds)
    ACHTUNG - command is an array of parameters, NOT a plain string
    example usage: measure(["luxconsole", "scene.lxs"])
    '''

    start = time.time()
    exec_cmd(command)
    end = time.time()
    return end - start




#print measure(["blender","-b","blender/blender_task/scene-Helicopter-27.blend","-F","JPEG","-x","1","-f","1"])
