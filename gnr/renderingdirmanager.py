from os import path

from golem.core.common import get_golem_path

PREV_FILE = "ui/nopreview.png"


def get_preview_file():
    return path.normpath(PREV_FILE)


def get_task_scripts_path():
    return path.join(get_golem_path(), "gnr", "task", "scripts")


def find_task_script(script_name):
    return path.join(get_task_scripts_path(), script_name)


def get_benchmarks_path():
    return path.join(get_golem_path(), "gnr", "benchmarks")


def get_test_task_path(root_path):
    return path.join(root_path, "task_test")


def get_test_task_tmp_path(root_path):
    return path.join(root_path, "task_tmp")


def get_tmp_path(node_name, task_id, root_path):
    # TODO: Is node name still needed?
    return path.join(root_path, "task", node_name, task_id, "tmp")
