import cPickle as pickle
import os

TEMPLATE = os.path.normpath("../save/testtask_template")
RESULT_GT = os.path.normpath("../save/testtask.gt")


def read_task(file_, file_dest):
    with open(file_) as f:
        task = pickle.load(f)
    dir_ = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    task.main_scene_file = os.path.normpath(os.path.join(dir_, task.main_scene_file))
    assert os.path.isfile(task.main_scene_file)
    task.main_program_file = os.path.normpath(os.path.join(dir_, task.main_program_file))
    assert os.path.isfile(task.main_program_file)
    task.resources = set([os.path.normpath(os.path.join(dir_, res))for res in task.resources])
    for res in task.resources:
        assert os.path.isfile(res)

    with open(file_dest, 'w') as f:
        pickle.dump(task, f)

if __name__ == "__main__":
    read_task(TEMPLATE, RESULT_GT)
