from golem.rpc.websockets import WebSocketRPCClientFactory


class WebSocketCLI(object):

    def __init__(self, cli_class, address, port):

        self.cli_class = cli_class
        self.cli = None
        self.address = address
        self.port = port

    def execute(self, *args, **kwargs):
        from twisted.internet import reactor, threads

        rpc_factory = WebSocketRPCClientFactory(self.address, self.port)

        def on_connected(_):
            rpc_client = rpc_factory.build_simple_client()
            self.cli = self.cli_class(rpc_client)
            threads.deferToThread(self.cli.execute, *args, **kwargs)

        def on_error(error):
            if reactor.running:
                reactor.stop()

            import sys
            sys.stderr.write(u"Error occurred: {}".format(error))

        def connect():
            rpc_factory.connect().addCallbacks(on_connected, on_error)

        reactor.callWhenRunning(connect)
        reactor.run()
