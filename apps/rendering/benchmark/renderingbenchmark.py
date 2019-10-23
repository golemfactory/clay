import logging

import os.path
import uuid

from apps.core.benchmark.benchmarkrunner import CoreBenchmark
from apps.rendering.resources.utils import handle_opencv_image_error
from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition
from apps.rendering.resources.imgrepr import OpenCVImgRepr

logger = logging.getLogger("apps.core")


class RenderingBenchmark(CoreBenchmark):

    def __init__(self):
        self._task_definition = RenderingTaskDefinition()
        self._task_definition.max_price = 100
        self._task_definition.resolution = [200, 100]
        self._task_definition.timeout = 10000
        self._task_definition.subtask_timeout = 10000
        self._task_definition.resources = set()
        self._task_definition.subtasks_count = 1
        self._task_definition.start_task = 1
        self._task_definition.task_id = str(uuid.uuid4())

        # magic constant obtained experimentally
        self._normalization_constant = 9500

    @property
    def normalization_constant(self):
        return self._normalization_constant

    @property
    def task_definition(self):
        return self._task_definition

    def find_resources(self):
        return set()

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
        with handle_opencv_image_error(logger):
            image = OpenCVImgRepr.from_image_file(filename)
            img_size = image.get_size()
            expected = self._task_definition.resolution
            if tuple(img_size) == tuple(expected):
                return True
            logger.warning("Bad resolution\nExpected %sx%s, but got %sx%s",
                           expected[0], expected[1], img_size[0], img_size[1])
        return False

    def verify_log(self, filename):
        with open(filename, 'r') as f:
            content = f.read()
        if "error" in content.lower():
            logger.warning("Found error in " + filename)
            return False
        return True
