from pathlib import Path

from golem.core.common import get_golem_path
from golem.interface.command import group, command
from golem.rpc.session import Client


@group(help="Show and accept terms of use")
class Terms:

    client: Client

    @command(help="Show terms of use")
    def show(self):  # pylint: disable=no-self-use
        terms_path = Path(get_golem_path()) / 'golem' / 'TERMS'
        return terms_path.read_text()

    @command(help="Accept terms of use")
    def accept(self):
        self.client.accept_terms()
        return "Terms of use have been accepted."
