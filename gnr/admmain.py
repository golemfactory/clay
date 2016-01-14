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

    try:
        start_app(logic, app, gui, rendering=True, start_add_task_client=False, start_add_task_server=False)
    finally:
        try:
            logic.client.task_server.task_computer.end_task()
        except Exception as ex:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Exception when closing Golem {}".format(ex))
        sys.exit(0)


if __name__ == "__main__":
    freeze_support()
    main()
