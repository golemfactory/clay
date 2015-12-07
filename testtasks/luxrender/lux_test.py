from testtasks.execution_time_measure import measure
from testtasks.dir_hash_builder import get_hash_of_dir, get_current_directory
import os
import sys
from PIL import Image

# normalization constant, obtained experimentally
MAGIC_CONSTANT = 34098
# hash of the test task
EXPECTED_CHECKSUM = "3a5567f7a564a6dc7aeb53a6d6ad902b5a7bbc43"
EXPECTED_PNG_SIZE = (201, 268)

def lux_performance():
    '''
    returns time (in seconds) needed to render the example scene
    '''
    output_filename_base = "out"
    current_dir = get_current_directory(sys.modules[__name__].__file__)
    directory = os.path.join(current_dir, r'lux_task')
    output_path = os.path.join(directory, output_filename_base)
    checksum = get_hash_of_dir(directory)
    if checksum == "-1":
        return -1.
    if str(checksum) != EXPECTED_CHECKSUM:
        print str(checksum)
        return -1.
    
    performance = MAGIC_CONSTANT / measure(["luxconsole", 
                                            os.path.join(directory, r'schoolcorridor.lxs'),
                                            "-o",
                                            output_path
                                          ])
    
    output_file_path = output_path + ".png"
    try:
        image = Image.open(output_file_path)
    except:
        return -1.
    if(image.size != EXPECTED_PNG_SIZE):
        return -1.
    return performance
