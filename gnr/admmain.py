import os

from gnrstartapp import start_app, config_logging
from renderingadmapplicationlogic import RenderingAdmApplicationLogic
from gnr.ui.administrationmainwindow import AdministrationMainWindow
from gnr.application import GNRGui
from gnr.customizers.renderingadmmainwindowcustomizer import RenderingAdmMainWindowCustomizer

from golem.tools.uigen import gen_ui_files
gen_ui_files(os.path.join(os.path.dirname(__file__), "ui"))


def main():
    config_logging()

    logic = RenderingAdmApplicationLogic()
    app = GNRGui(logic, AdministrationMainWindow)
    gui = RenderingAdmMainWindowCustomizer

    start_app(logic, app, gui, rendering=True, start_add_task_client=False, start_add_task_server=False)


from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()
    main()
