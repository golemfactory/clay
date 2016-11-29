#!/usr/bin/env python
"""
Converts an old-school Blender task definition in pickled or JSON format to
an equivalent task definition that can be run with Docker image 'golem/blender'.
"""
import json
import jsonpickle
import pickle
import sys
from os import path

from apps.blender.blenderenvironment import BlenderEnvironment
from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition

output_file = None
task_def = None

if len(sys.argv) == 3:
    output_file = sys.argv[2]
    if sys.argv[1].endswith(".gt"):
        with open(sys.argv[1], 'r') as infile:
            task_def = pickle.load(infile)
    elif sys.argv[1].endswith(".json"):
        with open(sys.argv[1], "r") as infile:
            task_def = jsonpickle.decode(infile.read())

if not isinstance(task_def, RenderingTaskDefinition):
    print "Usage: {} (<input-task>.gt|<input-task>.json) <output-task>.json"\
        .format(sys.argv[0])
    sys.exit(1)

# Replace BlenderEnvironment with BlenderDockerEnvironment
task_def.renderer_options.environment = BlenderEnvironment()

BLENDER_TASK_SCRIPT = path.normpath("/gnr/task/scripts/blendertask.py")
DOCKER_TASK_SCRIPT = path.normpath("/gnr/task/scripts/docker_blendertask.py")

# Replace main script file 'blendertask.py' with 'docker_blendertask.py':
task_def.main_program_file = \
    task_def.main_program_file.replace(BLENDER_TASK_SCRIPT, DOCKER_TASK_SCRIPT)
new_resources = set(path.replace(BLENDER_TASK_SCRIPT, DOCKER_TASK_SCRIPT)
                    for path in task_def.resources)
task_def.resources = new_resources

# Add docker images to task definition
task_def.docker_images = BlenderEnvironment().docker_images

with open(output_file, "w") as outfile:
    json_str = jsonpickle.encode(task_def)
    # For pretty printing we need to read the json back :(
    json_dict = json.loads(json_str)
    json.dump(json_dict, outfile, indent=2, separators=(',', ':'))
