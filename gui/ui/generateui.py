import os

from golem.core.common import get_golem_path
from golem.tools.uigen import gen_ui_files


def generate_ui_files():
    golem_path = get_golem_path()
    ui_path = os.path.normpath(os.path.join(golem_path, "gnr/ui"))
    gen_ui_files(ui_path)
