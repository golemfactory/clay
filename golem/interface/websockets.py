from golem.rpc.websockets import WebSocketRPCClientFactory


class WebSocketCLI(object):

    def __init__(self, cli_class, address, port):

        self.cli_class = cli_class
        self.cli = None
        self.rpc = None
        self.address = address
        self.port = port

    def execute(self, *args, **kwargs):
        from twisted.internet import reactor, threads

        self.rpc = WebSocketRPCClientFactory(self.address, self.port,
                                             on_disconnect=self.shutdown)

        def on_connected(_):
            rpc_client = self.rpc.build_simple_client()
            self.cli = self.cli_class(rpc_client)
            threads.deferToThread(self.cli.execute, *args, **kwargs).addBoth(self.shutdown)

        def on_error(error):
            import sys
            sys.stderr.write(u"Error occurred: {}".format(error))
            self.shutdown()

        def connect():
            self.rpc.connect().addCallbacks(on_connected, on_error)

        reactor.callWhenRunning(connect)
        reactor.run()

    def shutdown(self, *_):
        from twisted.internet import reactor
        from twisted.internet.error import ReactorNotRunning

        if self.cli:
            self.cli.shutdown()
        if self.rpc:
            self.rpc.disconnect()

        try:
            reactor.stop()
        except ReactorNotRunning:
            pass
