import cPickle as pickle
import os


def read_task(file_, file_dest):
    with open(file_) as f:
        task = pickle.load(f)
    dir_ = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
    task.main_scene_file = os.path.normpath(os.path.join(dir_, task.main_scene_file))
    task.main_program_file = os.path.normpath(os.path.join(dir_, task.main_program_file))
    task.resources = set([os.path.normpath(os.path.join(dir_, res))for res in task.resources])

    with open(file_dest, 'w') as f:
        pickle.dump(task, f)

if __name__ == "__main__":
    read_task('../save/testtask_template', '../save/testtask.gt')
