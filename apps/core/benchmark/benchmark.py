import logging

from PIL import Image

from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition

logger = logging.getLogger("gnr.benchmarks")


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

    def query_benchmark_task_definition(self):
        return self.task_definition
    
    def find_resources(self):
        return set()

    # result is a list of files produced in computation (logs and imgs)
    # if img has a different format, you need to implement this method in a subclass
    def verify_result(self, result):
        for f in result:
            if f.lower().endswith(".png") and not self.verify_img(f):
                return False
            elif f.lower().endswith(".log") and not self.verify_log(f):
                return False
        return True

    def verify_img(self, filename):
        try:
            image = Image.open(filename)
        except:
            import traceback
            # Print the stack traceback
            traceback.print_exc()
            return False
        img_size = image.size
        image.close()
        expected = self.task_definition.resolution
        if img_size[0] == expected[0] and img_size[1] == expected[1]:
            return True
        logger.warning("Bad resolution")
        logger.warning("Expected {}x{}, but got {}x{}".format(expected[0], expected[1],
                                                            img_size[0], img_size[1]))
        return False
    
    def verify_log(self, filename):
        fd = open(filename, "r")
        content = fd.read()
        fd.close()
        if "error" in content.lower():
            logger.warning("Found error in " + filename)
            return False
        return True
