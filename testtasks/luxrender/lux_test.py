from testtasks.execution_time_measure import measure
from testtasks.dir_hash_builder import get_hash_of_dir, get_current_directory
import os

EXPECTED_CHECKSUM = "725ad6c8c3391c730708bf3619bfd236690fef29"

def lux_performance():
    '''
    returns time (in seconds) needed to render the example scene
    '''
    current_dir = get_current_directory(__file__)
    directory = os.path.join(current_dir, r'lux_task')
    checksum = get_hash_of_dir(directory)
    if checksum == "-1":
        return -1.
    if str(checksum) != EXPECTED_CHECKSUM:
        return -1.
    return measure(["luxconsole", "lux_task/scene-Helicopter-27.Scene.00001.lxs"])
