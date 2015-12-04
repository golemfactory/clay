from testtasks.execution_time_measure import measure
from testtasks.dir_hash_builder import get_hash_of_dir, get_current_directory
import os
import sys

# normalization constant, obtained experimentally
MAGIC_CONSTANT = 38956
# hash of the test task
EXPECTED_CHECKSUM = "4f348c63485f76efcc26a8264cea003936ffbf46"

def blender_performance():
    '''
    returns time (in seconds) needed to render the example scene
    '''
    current_dir = get_current_directory(sys.modules[__name__].__file__)
    directory = os.path.join(current_dir, r'blender_task')
    checksum = get_hash_of_dir(directory)
    if checksum == "-1":
        return -1.
    if str(checksum) != EXPECTED_CHECKSUM:
        return -1.
    return MAGIC_CONSTANT / measure(["blender","-b",os.path.join(directory, r'scene-Helicopter-27.blend'),"-F","JPEG","-x","1","-f","1"])
