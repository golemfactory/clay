import logging

import os.path
from PIL import Image

from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition

logger = logging.getLogger("apps.core")


class Benchmark(object):
    def __init__(self):
        self.task_definition = RenderingTaskDefinition()
        self.task_definition.max_price = 100
        self.task_definition.resolution = [200, 100]
        self.task_definition.full_task_timeout = 10000
        self.task_definition.subtask_timeout = 10000
        self.task_definition.optimize_total = False
        self.task_definition.resources = set()
        self.task_definition.total_tasks = 1
        self.task_definition.total_subtasks = 1
        self.task_definition.start_task = 1
        self.task_definition.end_task = 1
        
        # magic constant obtained experimentally
        self.normalization_constant = 9500

    def find_resources(self):
        return set()

    # result is a list of files produced in computation (logs and imgs)
    # if img has a different format, you need to implement this method in a subclass
    def verify_result(self, result):
        for filepath in result:
            root, ext = os.path.splitext(filepath)
            ext = ext.lower()
            if ext == '.png' and not self.verify_img(filepath):
                return False
            elif ext == '.log' and not self.verify_log(filepath):
                return False
        return True

    def verify_img(self, filename):
        try:
            image = Image.open(filename)
        except:
            logger.warning('Error during image processing:', exc_info=True)
            return False
        img_size = image.size
        image.close()
        expected = self.task_definition.resolution
        if tuple(img_size) == tuple(expected):
            return True
        logger.warning("Bad resolution\nExpected {}x{}, but got {}x{}".format(expected[0], expected[1], img_size[0], img_size[1]))
        return False
    
    def verify_log(self, filename):
        with open(filename, 'r') as f:
            content = f.read()
        if "error" in content.lower():
            logger.warning("Found error in " + filename)
            return False
        return True
