import subprocess
import sys
import os
import json

import houdini_python

houdini_python.enableHouModule()
import hou


def exec_cmd(cmd):
    pc = subprocess.Popen(cmd)
    return pc.wait()




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
def build_output( output, input ):

    if output:
    	return [  "-o", output ]
    else:
        base_path = os.path.dirname( input )
	path = os.path.join( base_path, "output/render.$F4.png" )
    	return [  "-o", path ]

# ================================
#
def build_command( file, renderer, start_frame, end_frame, output ):

    # We can load this path from /houdini/installation-info.json
    hrender_path = "/opt/hfs16.5/bin/hrender.py"
    #hrender_path = "apps/houdini/resources/scripts/hrender.py"

    command = [ "hython" ]
    command += [ hrender_path ]
    command += ["-e"]
    command += ["-v"]
    command += build_renderer_param( renderer )
    command += [ file ]
    command += build_frames_params( start_frame, end_frame )
    command += build_output( output, file )

    return command


# ================================
#
def load_task_definition( file ):

    task_definition = dict()

    with open( file, 'r' ) as infile:
        task_definition = json.load( infile )

    return task_definition

# ================================
#
def run_rendering( scene_file, renderer, start, end, output ):

	command = build_command( scene_file, renderer, start, end, output )
	print( "Executing command: " + str( command ) )

	exec_cmd( command )


def run():

	# hython /opt/hfs16.5.536/bin/hrender.py -e -d /out/mantra_ipr /home/nieznanysprawiciel/Data/Houdini-examples/rop_example_bakeanimation.hipnc -f 0 30

    if len( sys.argv ) > 2:
    	scene_file = sys.argv[ 1 ]
    	renderer = sys.argv[ 2 ]
    	start = sys.argv[ 3 ]
    	end = sys.argv[ 4 ]
    	output = None

    	if len( sys.argv ) > 5:
    	    output = sys.argv[ 5 ]

        run_rendering( scene_file, renderer, start, end, output )

    else:

        task_definition_file = sys.argv[ 1 ]
        task_definition = load_task_definition( task_definition_file )

    	scene_file = task_definition[ "scene_file" ]
    	renderer = task_definition[ "render_node" ]
    	start = task_definition[ "start_frame" ]
    	end = task_definition[ "end_frame" ]
    	output = task_definition[ "output" ]

        run_rendering( scene_file, renderer, start, end, output )

	# python /home/nieznanysprawiciel/Repos/Golem/HoudiniDockerBuild/scripts/houdini_render.py /home/nieznanysprawiciel/Data/Houdini/bullet-bendable/example_bullet_bendable.hip /out/mantra_ipr 0 70

if __name__ == "__main__":
    run()
