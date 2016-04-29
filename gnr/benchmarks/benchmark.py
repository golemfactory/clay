import logging
import os
from PIL import Image

from gnr.renderingtaskstate import RenderingTaskDefinition

logger = logging.getLogger(__name__)

class Benchmark():
    def __init__(self):
        self.task_definition = RenderingTaskDefinition()
        self.task_definition.max_price = 100
        self.task_definition.resolution = [100, 100]
        self.task_definition.full_task_timeout = 10000
        self.task_definition.subtask_timeout = 10000
        self.task_definition.optimize_total = False
        self.task_definition.resources = set()

    def query_benchmark_task_definition(self):
        return self.task_definition
    
    def find_resources(self):
        return set()


    # result is a list of files produced in computation (logs and imgs)
    def verify_result(self, result):
        logger.debug("in verify_result")
        for f in result:
            logger.debug("Checking file " + f)
            if f.lower().endswith(".png") and not self.verify_img(f):
                return False
            elif f.lower().endswith(".log") and not self.verify_log(f):
                return False
        return True
                
        
    def verify_img(self, filename):
        logger.debug("in verify_img")
        try:
            image = Image.open(filename)
        except:
            logger.debug("Failed to open img file: " + filename)
            import traceback
            # Print the stack traceback
            traceback.print_exc()
            return False
        logger.debug("Successfully opened img file: " + filename)
        if(image.size == self.task_definition.resolution):
            logger.debug("Resolution matches! Hurray!")
            return True
        logger.debug("Bad resolution")
        return False
    
    def verify_log(self, filename):
        logger.debug("in verify_log")
        fd = open(filename, "r")
        content = fd.read()
        fd.close()
        if "error" in content.lower():
            logger.debug("Found error in " + filename)
            return False
        logger.debug("Errors not found in {}. Hurray!".format(filename))
        return True