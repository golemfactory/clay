import jsonpickle as json
import os

from golem.core.common import get_golem_path
from golem.core.simpleenv import get_local_datadir

TEMPLATE = os.path.join(get_golem_path(), "save", "testtask_template")
RESULT_GT = os.path.join(get_local_datadir("save"), "testtask.gt")


def read_task(file_, file_dest):
    with open(file_) as f:
        task = json.load(f)
    task.main_scene_file = os.path.normpath(os.path.join(get_golem_path(), task.main_scene_file))
    if not os.path.isfile(task.main_scene_file):
        raise IOError("incorrect main scene path: {}".format(task.main_scene_file))
    task.main_program_file = os.path.normpath(os.path.join(get_golem_path(), task.main_program_file))
    if not os.path.isfile(task.main_program_file):
        raise IOError("incorrect main program path: {}".format(task.main_program_file))
    task.resources = {os.path.normpath(os.path.join(get_golem_path(), res))for res in task.resources}
    for res in task.resources:
        if not os.path.isfile(res):
            raise IOError("incorrect resource path: {}".format(res))

    if not os.path.isdir(os.path.dirname(file_dest)):
        os.makedirs(os.path.dirname(file_dest))

    with open(file_dest, 'w') as f:
        json.dump(task, f)

if __name__ == "__main__":
    read_task(TEMPLATE, RESULT_GT)
