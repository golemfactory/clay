from os import path, listdir
import logging

from golem.core.common import get_golem_path

logger = logging.getLogger("gnr.app")

PREV_FILE = "ui/nopreview.png"


def get_preview_file():
    return path.normpath(PREV_FILE)


def get_task_scripts_path():
    return path.join(get_golem_path(), "gnr", "task", "scripts")


def find_task_script(task__file__, script_name):
    scripts_path = path.abspath(path.join(path.dirname(path.abspath(task__file__)), "..", "resources", "scripts"))
    files = listdir(scripts_path)
    for f in files:
        if f.lower() == script_name.lower():
            return path.join(scripts_path, f)
    logger.error("Script file does not exist!")


def get_test_task_path(root_path):
    return path.join(root_path, "task_test")


def get_test_task_tmp_path(root_path):
    return path.join(root_path, "task_tmp")


def get_tmp_path(task_id, root_path):
    # TODO: Is node name still needed?
    return path.join(root_path, "task", task_id, "tmp")
