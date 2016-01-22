from gnr.benchmarks.execution_time_measure import measure
from gnr.benchmarks.dir_hash_builder import get_hash_of_dir, get_current_directory
import os
import sys
from PIL import Image

# normalization constant, obtained experimentally
MAGIC_CONSTANT = 38956
# hash of the test task
EXPECTED_CHECKSUM = "4f348c63485f76efcc26a8264cea003936ffbf46"
EXPECTED_JPG_SIZE = (576, 324)

def blender_performance():
    '''
    returns time (in seconds) needed to render the example scene
    '''
    output_filename_base = "out"
    current_dir = get_current_directory(sys.modules[__name__].__file__)
    directory = os.path.join(current_dir, r'blender_task')
    output_path = os.path.join(directory, output_filename_base) + "1.jpg"
    checksum = get_hash_of_dir(directory)
    if checksum == "-1":
        return -1.
    if str(checksum) != EXPECTED_CHECKSUM:
        return -1.
    
    performance = MAGIC_CONSTANT / measure(["blender",
                                     "-b",
                                     os.path.join(directory, r'scene-Helicopter-27.blend'),
                                     "-o",
                                     os.path.join(directory, output_filename_base) + "#",
                                     "-F",
                                     "JPEG",
                                     "-x",
                                     "1",
                                     "-f",
                                     "1"
                                   ])
    
    try:
        image = Image.open(output_path)
    except:
        return -1.
    if(image.size != EXPECTED_JPG_SIZE):
        return -1.
    return performance
    