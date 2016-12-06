from golem.rpc.mapping.core import CORE_METHOD_MAP
from golem.rpc.session import Session, Client, WebSocketAddress


class WebSocketCLI(object):

    class NoConnection(object):
        def __getattribute__(self, item):
            raise Exception("Cannot connect to Golem instance")

    def __init__(self, cli, host, port, realm, ssl=False):
        address = WebSocketAddress(host, port, realm, ssl)

        self.cli = cli
        self.session = Session(address)

    def execute(self, *args, **kwargs):
        from twisted.internet import reactor, threads

        def on_connected(_):
            core_client = Client(self.session, CORE_METHOD_MAP)
            self.cli.register_client(core_client)
            threads.deferToThread(self.cli.execute, *args, **kwargs).addBoth(self.shutdown)

        def on_error(_):
            self.cli.register_client(WebSocketCLI.NoConnection())
            self.cli.execute(*args, **kwargs)
            self.shutdown()

        def connect():
            self.session.connect().addCallbacks(on_connected, on_error)

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
