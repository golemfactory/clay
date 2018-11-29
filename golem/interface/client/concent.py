import typing

import html2text

from golem.core.deferred import sync_wait
from golem.interface.command import group, command

if typing.TYPE_CHECKING:
    from golem.rpc.session import ClientProxy  # noqa pylint: disable=unused-import


@group(help="Concent Service")
class Concent:
    client: 'ClientProxy'


@group(parent=Concent, help="Terms of Use")
class Terms:
    client: 'ClientProxy'

    @classmethod
    def _call(cls, uri, *args, **kwargs):
        return Concent.client._call(  # pylint: disable=protected-access
            f"golem.concent.terms.{uri}",
            *args,
            **kwargs,
        )

    @command(help="Show terms of use")
    def show(self):  # pylint: disable=no-self-use
        terms = sync_wait(self._call("show"))
        return html2text.html2text(terms)

    @command(help="Accept terms of use")
    def accept(self):
        self._call("accept")
        return "Concent terms of use have been accepted."
