import subprocess
import sys
import os
import json
import params


######################################################################################
## This is entry point for houdini rendering task. This file makes 2 things:
## - setups Houdini environment variables
## - runs rendering
##
## To set environment we must execute houdini_setup_bash script. But this scripts
## sets environment variables, that must be visible for rendering python script. We can't just
## source houdini_setup_bash from this file, because such operation spawns child subprocess
## and after execution, variables are no longer visible.
## The solution is a little bit tricky and cumbersome. docker_houdinitask.py spawns new process,
## that executes houdini_invoker.sh script, which source houdini_setup_bash and then runs python
## rendering script. Since python is executed as a child process, it sees all environment variables
## that were set previously.


# ================================
#
def exec_cmd(cmd):

    try:
        pc = subprocess.Popen(cmd)
        return pc.wait()
    except Exception as e:
        message = "While executing command: " + str( cmd ) + "\nWorking directory: " +  os.getcwd()
        raise type(e), type(e)(e.message + message), sys.exc_info()[2]


# ================================
#
def save_task_definition( file, dict ):
    with open(file, 'w') as outfile:
        json.dump(dict, outfile)

# ================================
#
def get_houdini_setup_dir( file ):

    houdini_installation = dict()

    with open( file, 'r' ) as infile:
        houdini_installation = json.load( infile )

    return os.path.join( houdini_installation[ "install_dir" ], houdini_installation[ "version" ] )


# ================================
#
def setup_houdini_end_render( installation_info, task_definition_file ):

    houdini_dir = get_houdini_setup_dir( installation_info )

    os.chdir( "/golem/scripts/" )

    command = [ "./houdini_invoker.sh", houdini_dir, task_definition_file ]
    exec_cmd( command )


# ================================
#
def run():

    # Docker image build script saves installation info in this file.
    # Change this variable to test scripts locally (outside docker container).
    #installation_info = "/home/nieznanysprawiciel/Repos/Golem/HoudiniDockerBuild/install/houdini-installation.json"
    installation_info = "/houdini/houdini-installation.json"

    task_definition_file = "/golem/work/task_definition.json"

    save_task_definition( task_definition_file, params.render_params )
    setup_houdini_end_render( installation_info, task_definition_file )


if __name__ == "__main__":
    run()
