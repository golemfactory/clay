from os import path

from golem.core.common import get_golem_path


def get_preview_file():
    return path.join(get_golem_path(), "gui", "view", "nopreview.png")