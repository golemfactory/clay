import click
import logging
from twisted.internet.defer import inlineCallbacks

from golem.core.common import config_logging
from golem.node import OptNode
from golem.rpc.mapping.rpcmethodnames import NAMESPACES
from golem.rpc.session import Session, WebSocketAddress


class EventLoggingSession(Session):

    def __init__(self, logger, address, methods=None, events=None):
        super(EventLoggingSession, self).__init__(address, methods, events)
        self.logger = logger

    @inlineCallbacks
    def onJoin(self, details):
        yield super(EventLoggingSession, self).onJoin(details)
        self.logger.info('| onJoin(%s)', details)

    def onUserError(self, fail, msg):
        super(EventLoggingSession, self).onUserError(fail, msg)
        self.logger.error('| onUserError %s %s', fail, msg)

    def onConnect(self):
        super(EventLoggingSession, self).onConnect()
        self.logger.info('| onConnect')

    def onClose(self, wasClean):
        super(EventLoggingSession, self).onClose(wasClean)
        self.logger.info('| onClose(wasClean=%s)', wasClean)

    def onLeave(self, details):
        super(EventLoggingSession, self).onLeave(details)
        self.logger.info('| onLeave(details=%s)', details)

    def onDisconnect(self):
        super(EventLoggingSession, self).onDisconnect()
        self.logger.info('| onDisconnect')


def build_handler(logger, evt_name):
    def handler(*args, **kwargs):
        logger.info('%s %s %s', evt_name, args, kwargs)
    return handler


def build_handlers(logger):
    handlers = set()
    for ns in NAMESPACES:
        for prop, value in ns.__dict__.items():
            if is_event(prop, value):
                entry = build_handler(logger, value), value
                handlers.add(entry)
    return handlers


def is_event(prop, value):
    return not prop.startswith('_') \
           and isinstance(value, basestring) \
           and value.startswith('evt.')


@click.command()
@click.option('--datadir', '-d', type=click.Path())
@click.option('--rpc-address', '-r',
              multiple=False,
              callback=OptNode.parse_rpc_address,
              help="RPC server address: <ip_addr>:<port>")
def main(datadir, rpc_address):
    from twisted.internet import reactor

    if rpc_address:
        host = rpc_address.address
        port = rpc_address.port
    else:
        host = 'localhost'
        port = 61000

    config_logging(datadir=datadir)
    logger = logging.getLogger('events')

    address = WebSocketAddress(host, port, realm=u'golem')
    events = build_handlers(logger)

    rpc_session = EventLoggingSession(logger, address, events=events)
    rpc_session.connect(auto_reconnect=True)

    reactor.run()


if __name__ == '__main__':
    main()
