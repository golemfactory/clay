from multiprocessing import freeze_support

import click

from startapp import start_app


@click.command()
@click.option('--datadir', '-d', type=click.Path())
def main(datadir):
    start_app(datadir=datadir, rendering=True, transaction_system=True)

if __name__ == "__main__":
    freeze_support()
    main()
