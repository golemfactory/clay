from multiprocessing import freeze_support
from os import path

import click

from gnrstartapp import start_app, config_logging
from renderingapplicationlogic import RenderingApplicationLogic
from gnr.ui.appmainwindow import AppMainWindow
from gnr.application import GNRGui
from gnr.customizers.renderingmainwindowcustomizer import RenderingMainWindowCustomizer


@click.command()
@click.option('--datadir', '-d', type=click.Path())
def main(datadir):
    if datadir:
        config_logging(path.join(datadir, 'golem.log'))
    else:
        config_logging()

    logic = RenderingApplicationLogic()
    app = GNRGui(logic, AppMainWindow)
    gui = RenderingMainWindowCustomizer

    start_app(logic, app, gui, datadir=datadir, rendering=True)

if __name__ == "__main__":
    freeze_support()
    main()
