import sys
import typing

import html2text

from golem.core.deferred import sync_wait
from golem.interface.command import group, command

if typing.TYPE_CHECKING:
    from golem.rpc.session import ClientProxy


def yes_no(prompt: str, default: str = 'y') -> bool:
    value = 'maybe'

    while value not in ('y', 'yes', 'n', 'no'):
        sys.stdout.write(f'{prompt} [{default}]: ')
        sys.stdout.flush()

        resp = sys.stdin.readline()
        value = resp.strip().lower() or default

    return value[0] == 'y'


def read_accept_options() -> typing.Dict[str, bool]:
    values = {True: 'ENABLED', False: 'DISABLED'}
    options = dict()

    for entry in ('monitor', 'talkback'):
        value = yes_no(f'Enable {entry}?')
        options[f'enable_{entry}'] = value
        print(f'  {entry} will be {values[value]}')

    return options


@group(help="Show and accept terms of use")
class Terms:

    client: ClientProxy

    @command(help="Show terms of use")
    def show(self):  # pylint: disable=no-self-use
        terms = sync_wait(self.client.show_terms())
        return html2text.html2text(terms)

    @command(help="Accept terms of use")
    def accept(self):
        options = read_accept_options()
        self.client.accept_terms(**options)
        return "Terms of use have been accepted."
