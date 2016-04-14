import click
from multiprocessing import freeze_support

from gnrstartapp import start_app, config_logging
from renderingadmapplicationlogic import RenderingAdmApplicationLogic
from gnr.ui.administrationmainwindow import AdministrationMainWindow
from gnr.application import GNRGui
from gnr.customizers.renderingadmmainwindowcustomizer import RenderingAdmMainWindowCustomizer

from golem.core.simpleenv import _get_local_datadir


@click.command()
@click.option('--datadir', '-d', type=click.Path(),
              default=_get_local_datadir('gnr'))
def main(datadir):
    config_logging()

    logic = RenderingAdmApplicationLogic()
    app = GNRGui(logic, AdministrationMainWindow)
    gui = RenderingAdmMainWindowCustomizer

    start_app(logic, app, gui, datadir=datadir, rendering=True,
              start_add_task_client=False, start_add_task_server=False)


if __name__ == "__main__":
    freeze_support()
    main()
