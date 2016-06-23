from multiprocessing import freeze_support

import click

from gnrstartapp import start_app, config_logging


@click.command()
@click.option('--datadir', '-d', type=click.Path())
def main(datadir):
    config_logging()
    start_app(datadir=datadir, rendering=True)

if __name__ == "__main__":
    freeze_support()
    main()
