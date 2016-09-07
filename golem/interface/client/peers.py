from golem.interface.command import group


@group(help="Peer management commands")
class Peers(object):

    client = None
