import sys

from golem.rpc.common import CROSSBAR_REALM, CROSSBAR_PORT, CROSSBAR_HOST
from golem.rpc.mapping.rpcmethodnames import CORE_METHOD_MAP, NODE_METHOD_MAP
from golem.rpc.session import Session, Client, WebSocketAddress


class WebSocketCLI(object):

    class NoConnection(object):
        def __getattribute__(self, item):
            raise Exception("Cannot connect to Golem instance")

    def __init__(self, cli,  # pylint: disable=too-many-arguments
                 host: str = CROSSBAR_HOST,
                 port: int = CROSSBAR_PORT,
                 realm: str = CROSSBAR_REALM,
                 ssl: bool = True) -> None:

        address = WebSocketAddress(host, port, realm, ssl)

        self.cli = cli
        self.session = Session(address)

    def execute(self, *args, **kwargs):
        from twisted.internet import reactor, threads

        def on_connected(_):
            methods = {**CORE_METHOD_MAP, **NODE_METHOD_MAP}
            core_client = Client(self.session, methods)
            self.cli.register_client(core_client)
            threads.deferToThread(self.cli.execute, *args, **kwargs) \
                .addBoth(self.shutdown)

        def on_error(error):
            sys.stderr.write("Error connecting to Golem instance ({}): {}\n"
                             .format(self.session.address, error))

            self.cli.register_client(WebSocketCLI.NoConnection())
            self.cli.execute(*args, **kwargs)
            self.shutdown()

        def connect():
            self.session.connect(
                auto_reconnect=False
            ).addCallbacks(on_connected, on_error)

        reactor.callWhenRunning(connect)
        reactor.run()

    def shutdown(self, *_):
        from twisted.internet import reactor
        from twisted.internet.error import ReactorNotRunning

        if self.cli:
            self.cli.shutdown()
        if self.session:
            self.session.disconnect()

        try:
            reactor.stop()
        except ReactorNotRunning:
            pass
