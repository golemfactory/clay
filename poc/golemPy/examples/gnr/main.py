import sys
import os
import logging
import logging.config

sys.path.append(os.environ.get('GOLEM'))

from tools.uigen import gen_ui_files

if os.path.normpath(os.getcwd()) == os.path.normpath(os.path.join(os.environ.get('GOLEM'), "examples/gnr")):
    gen_ui_files("ui")

from renderingapplicationlogic import RenderingApplicationLogic
from examples.gnr.ui.renderingmainwindow import RenderingMainWindow
from examples.gnr.application import GNRGui
from examples.gnr.customizers.renderingmainwindowcustomizer import RenderingMainWindowCustomizer
from gnrstartapp import start_app


def main():
    if os.path.normpath(os.getcwd()) == os.path.normpath(os.path.join(os.environ.get('GOLEM'), "examples/gnr")):
        logging.config.fileConfig('logging.ini', disable_existing_loggers=False)

    logic = RenderingApplicationLogic()
    app = GNRGui(logic, RenderingMainWindow)
    gui = RenderingMainWindowCustomizer

    start_app(logic, app, gui, rendering=True)


from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()
    main()
