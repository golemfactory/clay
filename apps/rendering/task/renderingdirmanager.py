from os import path, listdir
import logging

logger = logging.getLogger("apps.rendering")

PREV_FILE = "view/nopreview.png"


def get_preview_file():
    return path.normpath(PREV_FILE)


def find_task_script(task_dir, script_name):
    scripts_path = path.abspath(path.join(task_dir, "resources", "scripts"))
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
