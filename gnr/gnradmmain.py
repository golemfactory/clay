from gnrstartapp import start_app, config_logging
from gnr.gnradmapplicationlogic import GNRAdmApplicationLogic
from gnr.application import GNRGui
from gnr.ui.mainwindow import GNRMainWindow
from gnr.customizers.gnradministratormainwindowcustomizer import GNRAdministratorMainWindowCustomizer


def main():
    config_logging()

    logic = GNRAdmApplicationLogic()
    app = GNRGui(logic, GNRMainWindow)
    gui = GNRAdministratorMainWindowCustomizer
    start_app(logic, app, gui, start_manager=True, start_info_server=True)


from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()
    main()
