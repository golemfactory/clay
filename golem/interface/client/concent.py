import typing

import html2text

from golem.core.deferred import sync_wait
from golem.interface.command import (
    Argument,
    command,
    group,
    customize_output)

if typing.TYPE_CHECKING:
    from golem.rpc.session import ClientProxy  # noqa pylint: disable=unused-import


on_off_arg = Argument(
    "on_off",
    choices=["on", "off"],
)


@group(help="Concent Service")
class Concent:
    client: 'ClientProxy'


@group(parent=Concent, help="Soft Switch")
class Switch:
    @classmethod
    def _call(cls, uri, *args, **kwargs):
        return Concent.client._call(  # pylint: disable=protected-access
            f"golem.concent.switch{uri}",
            *args,
            **kwargs,
        )

    @command(arguments=(on_off_arg, ))
    @customize_output('Concent switch turned {}.', ['on_off'],
                      include_call_time=True)
    def turn(self, on_off):
        return sync_wait(self._call(
            ".turn",
            on_off == "on",
        ))

    @command()
    def is_on(self):
        return sync_wait(self._call(""))


@group(parent=Concent, help="Terms of Use")
class Terms:
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
