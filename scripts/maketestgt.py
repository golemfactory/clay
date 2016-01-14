import cPickle as pickle
import os
import appdirs

from golem.core.common import get_golem_path

TEMPLATE = os.path.normpath(os.path.join(get_golem_path(), "save/testtask_template"))
RESULT_GT = os.path.normpath(os.path.join(appdirs.user_data_dir("golem"), "save/testtask.gt"))


def read_task(file_, file_dest):
    with open(file_) as f:
        task = pickle.load(f)
    task.main_scene_file = os.path.normpath(os.path.join(get_golem_path(), task.main_scene_file))
    assert os.path.isfile(task.main_scene_file)
    task.main_program_file = os.path.normpath(os.path.join(get_golem_path(), task.main_program_file))
    print task.main_program_file
    assert os.path.isfile(task.main_program_file)
    task.resources = set([os.path.normpath(os.path.join(get_golem_path(), res))for res in task.resources])
    for res in task.resources:
        assert os.path.isfile(res)

    if not os.path.isdir(os.path.dirname(file_dest)):
        os.makedirs(os.path.dirname(file_dest))

    with open(file_dest, 'w') as f:
        pickle.dump(task, f)

if __name__ == "__main__":
    read_task(TEMPLATE, RESULT_GT)
