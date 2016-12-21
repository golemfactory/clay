from os import path

from golem.core.common import get_golem_path


def get_preview_file():
    return path.join(get_golem_path(), "gui", "view", "nopreview.png")


def get_icons_list():
    icons = ["new.png", "task.png", "eye.png", "settings.png", "user.png"]
    return [path.join(get_golem_path(), "gui", "view", "img", icon) for icon in icons]