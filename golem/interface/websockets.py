import sys
import asyncio
import functools
from golem.rpc.mapping.core import CORE_METHOD_MAP
from golem.rpc.session import Session, Client, WebSocketAddress


class WebSocketCLI(object):

    class NoConnection(object):
        def __getattribute__(self, item):
            raise Exception("Cannot connect to Golem instance")

    def __init__(self, cli, host, port, realm='golem', ssl=False):
        address = WebSocketAddress(host, port, realm, ssl)

        self.cli = cli
        self.session = Session(address)

    def execute(self, *args, **kwargs):
        def on_connected(f):
            try:
                f.result()
            except Exception as exc:
                self.on_error(exc)
            else:
                core_client = Client(self.session, CORE_METHOD_MAP)
                self.cli.register_client(core_client)
                f = asyncio.get_event_loop().run_in_executor(None,
                    functools.partial(self.cli.execute, *args, **kwargs))
                f.add_done_callback(self.shutdown)

        def on_error(_):
            sys.stderr.write("Error connecting to Golem instance ({})\n"
                             .format(self.session.address))

            self.cli.register_client(WebSocketCLI.NoConnection())
            self.cli.execute(*args, **kwargs)
            self.shutdown()

        def connect():
            future = self.session.connect(
                auto_reconnect=False
            )
            future.add_done_callback(on_connected)

        import asyncio
        loop = asyncio.get_event_loop()
        loop.call_soon(connect)
        loop.run_forever()


    def shutdown(self, *_):
        if self.cli:
            self.cli.shutdown()
        if self.session:
            self.session.disconnect()

        loop = asyncio.get_event_loop()
        loop.stop()
