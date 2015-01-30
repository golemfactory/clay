import subprocess
import win32process

def execCmd( cmd ):
    pc = subprocess.Popen( cmd )
    win32process.SetPriorityClass(pc._handle, win32process.IDLE_PRIORITY_CLASS )

    pc.wait()
