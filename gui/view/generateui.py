import os

from golem.core.common import get_golem_path
from golem.tools.uigen import gen_ui_files


def generate_ui_files():
    golem_path = get_golem_path()
    print golem_path
    ui_path = os.path.normpath(os.path.join(golem_path, "gui", "view"))
    print ui_path
    gen_ui_files(ui_path)

    apps_path = os.path.normpath(os.path.join(golem_path, "apps"))
    apps_candidates = os.listdir(apps_path)
    apps = [os.path.join(apps_path, app) for app in apps_candidates if os.path.isdir(os.path.join(apps_path, app))]
    print apps
    for app in apps:
        ui_path = os.path.join(app, "gui", "view")
        print ui_path
        if os.path.isdir(ui_path):
            gen_ui_files(ui_path)