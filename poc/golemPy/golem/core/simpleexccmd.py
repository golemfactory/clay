import subprocess
import sys
import psutil

def isWindows():
    return sys.platform == 'win32'

def execCmd(cmd, nice = 20, wait = True):
    pc = subprocess.Popen(cmd)
    if isWindows():
        import win32process
        win32process.SetPriorityClass(pc._handle, win32process.IDLE_PRIORITY_CLASS)
    else:
        p = psutil.Process(pc.pid)
        p.set_nice(nice)

    if wait:
        pc.wait()
