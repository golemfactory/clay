import sys
from multiprocessing import freeze_support

from gnrstartapp import start_app, config_logging
from renderingadmapplicationlogic import RenderingAdmApplicationLogic
from gnr.ui.administrationmainwindow import AdministrationMainWindow
from gnr.application import GNRGui
from gnr.customizers.renderingadmmainwindowcustomizer import RenderingAdmMainWindowCustomizer


def main():
    config_logging()

    logic = RenderingAdmApplicationLogic()
    app = GNRGui(logic, AdministrationMainWindow)
    gui = RenderingAdmMainWindowCustomizer

    start_app(logic, app, gui, rendering=True, start_add_task_client=False, start_add_task_server=False)


if __name__ == "__main__":
    freeze_support()
    main()
