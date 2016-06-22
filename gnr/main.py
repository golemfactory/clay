from multiprocessing import freeze_support

import click

from gnrstartapp import start_app, config_logging
from renderingapplicationlogic import RenderingApplicationLogic


@click.command()
@click.option('--datadir', '-d', type=click.Path())
def main(datadir):
    config_logging()
    logic = RenderingApplicationLogic()
    start_app(logic, datadir=datadir, rendering=True)

if __name__ == "__main__":
    freeze_support()
    main()
