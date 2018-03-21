import html2text

from golem.core.deferred import sync_wait
from golem.interface.command import group, command
from golem.rpc.session import Client


@group(help="Show and accept terms of use")
class Terms:

    client: Client

    @command(help="Show terms of use")
    def show(self):  # pylint: disable=no-self-use
        terms = sync_wait(self.client.show_terms())
        return html2text.html2text(terms)

    @command(help="Accept terms of use")
    def accept(self):
        self.client.accept_terms()
        return "Terms of use have been accepted."
