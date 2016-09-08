import argparse
import sys

from golem.core.common import config_logging
from golem.interface.cli import CLI
from golem.interface.client.tasks import Tasks
from golem.interface.websockets import WebSocketCLI

# prevent 'unused' warnings
_ = {Tasks}


def main():
    # process initial arguments
    arguments = dict(
        interactive=('-i', '--interactive'),
        address=('-a', '--address'),
        port=('-p', '--port'),
    )

    parser = argparse.ArgumentParser()

    parser.add_argument(*arguments['interactive'], dest="interactive", action="store_true", default=False)
    parser.add_argument(*arguments['address'], dest="address", type=str, default='127.0.0.1')
    parser.add_argument(*arguments['port'], dest="port", type=int, default=60103)

    parsed, forwarded = parser.parse_known_args(sys.argv[1:])

    # setup logging if in interactive mode
    if parsed.interactive:
        config_logging("golem_cli.log")

    # run the cli
    cli = WebSocketCLI(CLI, address=parsed.address, port=parsed.port)
    cli.execute(forwarded, interactive=parsed.interactive)


if __name__ == '__main__':
    main()
