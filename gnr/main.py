from multiprocessing import freeze_support

import click

from golem.core.simpleenv import get_local_datadir

from gnrstartapp import start_app, config_logging
from renderingapplicationlogic import RenderingApplicationLogic
from gnr.ui.appmainwindow import AppMainWindow
from gnr.application import GNRGui
from gnr.customizers.renderingmainwindowcustomizer import RenderingMainWindowCustomizer


@click.command()
@click.option('--datadir', '-d', type=click.Path(),
              default=get_local_datadir('gnr'))
def main(datadir):
    config_logging()

    logic = RenderingApplicationLogic()
    app = GNRGui(logic, AppMainWindow)
    gui = RenderingMainWindowCustomizer

    start_app(logic, app, gui, rendering=True, datadir=datadir)

if __name__ == "__main__":
    freeze_support()
    main()
