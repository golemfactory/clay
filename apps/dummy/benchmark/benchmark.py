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

        # TODO change that
        self.dummy_task_path = join(get_golem_path(), "apps", "dummy", "test_data")

        td = self.task_definition = DummyTaskDefinition()

        td.set_defaults(DummyTaskDefaults())
        td.shared_data_files = [join(self.dummy_task_path, x) for x in td.shared_data_files]
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