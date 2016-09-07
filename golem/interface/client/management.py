import sys

from golem.interface.command import command


@command(name="exit", doc="Exit the interactive shell")
def management_exit():
    from twisted.internet import reactor
    if reactor.running:
        reactor.stop()
    sys.exit(0)
