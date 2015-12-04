from testtasks.execution_time_measure import measure
from testtasks.dir_hash_builder import get_hash_of_dir, get_current_directory
import os
import sys

# normalization constant, obtained experimentally
MAGIC_CONSTANT = 34098
# hash of the test task
EXPECTED_CHECKSUM = "b48040b48391b7c435a0fe27d1223b4c17cf9a78"

def lux_performance():
    '''
    returns time (in seconds) needed to render the example scene
    '''
    current_dir = get_current_directory(sys.modules[__name__].__file__)
    directory = os.path.join(current_dir, r'lux_task')
    checksum = get_hash_of_dir(directory)
    if checksum == "-1":
        return -1.
    if str(checksum) != EXPECTED_CHECKSUM:
        print str(checksum)
        return -1.
    return MAGIC_CONSTANT / measure(["luxconsole", os.path.join(directory, r'schoolcorridor.lxs')])
