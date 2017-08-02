import sys
import tempfile
from os import walk
from os.path import abspath, dirname, join

from apps.dummy.dummyenvironment import DummyTaskEnvironment
from apps.dummy.task.dummytaskstate import DummyTaskOptions, DummyTaskDefinition, DummyTaskDefaults
from golem.core.common import get_golem_path

APP_DIR = join(get_golem_path(), 'apps', 'dummy')

#TODO copied from LuxBenchmark, abstract away

class DummyBenchmark(object):
    def __init__(self):

        #TODO why is it that way? Where is examples/dummy?
        if hasattr(sys, 'frozen') and sys.frozen:
            self.dummy_task_path = join(dirname(sys.executable),
                                      'examples', 'dummy')
        else:
            self.dummy_task_path = join(dirname(abspath(__file__)), "test_task")

        td = self.task_definition = DummyTaskDefinition()

        td.set_defaults(DummyTaskDefaults())
        td.shared_data_file = join(self.dummy_task_path, td.shared_data_file)
        td.out_file_basename = join(tempfile.gettempdir(), td.out_file_basename)
        td.options = DummyTaskOptions()
        td.task_id = u"{}".format("dummy_benchmark")
        td.main_program_file = DummyTaskEnvironment().main_program_file
        td.resources = self.find_resources()

    def find_resources(self):
        selection = []
        for root, dirs, files in walk(self.dummy_task_path):
            for name in files:
                selection.append(join(root, name))
        return set(selection)