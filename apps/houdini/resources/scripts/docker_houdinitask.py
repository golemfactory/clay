import subprocess

import houdini_python

houdini_python.enableHouModule()
import hou


def exec_cmd(cmd):
    pc = subprocess.Popen(cmd)
    return pc.wait()



print( "Imported hou" )


# ================================
#
def build_renderer_param( renderer ):
    return [ "-d", renderer ]

# ================================
#
def build_frames_params( start_frame, end_frame ):
    return [  "-f", str( start_frame ), str( end_frame ) ]

# ================================
#
def build_command( file, renderer, start_frame, end_frame ):

    hrender_path = "/opt/hfs16.5.536/bin/hrender.py"
    #hrender_path = "apps/houdini/resources/scripts/hrender.py"

    command = [ "hython" ]
    command += [ hrender_path ]
    command += ["-e"]
    command += build_renderer_param( renderer )
    command += [ file ]
    command += build_frames_params( start_frame, end_frame )

    return command

# hython /opt/hfs16.5.536/bin/hrender.py -e -d /out/mantra_ipr /home/nieznanysprawiciel/Data/Houdini-examples/rop_example_bakeanimation.hipnc -f 0 30


command = build_command( "/home/nieznanysprawiciel/Data/Houdini-examples/rop_example_bakeanimation.hipnc", "/out/mantra_ipr", 0, 30 )
print( "Executing command: " + str( command ) )


exec_cmd( command )
