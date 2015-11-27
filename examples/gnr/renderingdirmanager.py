import os

TEST_RES_DIRECTORY = "testing_task_resources"
TEST_TMP_DIRECTORY = "testing_task_tmp"
RES_DIRECTORY = "res"
TMP_DIRECTORY = "tmp"
PREV_FILE = "ui/nopreview.png"


def get_test_task_directory():
    return TEST_RES_DIRECTORY


def get_preview_file():
    return PREV_FILE


def get_test_task_path(root_path):
    return os.path.join(root_path, TEST_RES_DIRECTORY)


def get_test_task_tmp_path(root_path):
    return os.path.join(root_path, TEST_TMP_DIRECTORY)


def get_tmp_path(client_id, task_id, root_path):
    return os.path.join(root_path, RES_DIRECTORY, client_id, task_id, TMP_DIRECTORY)
