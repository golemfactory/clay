import sys

from golem.rpc.common import CROSSBAR_REALM, CROSSBAR_PORT, CROSSBAR_HOST
from golem.rpc.session import Session, WebSocketAddress

from scripts.concent_node_tests.params import (
    REQUESTOR_RPC_PORT, PROVIDER_RPC_PORT)


class RPCClient:

    def __init__(self,
                 host: str = CROSSBAR_HOST,
                 port: int = CROSSBAR_PORT,
                 realm: str = CROSSBAR_REALM,
                 ssl: bool = True) -> None:

        address = WebSocketAddress(host, port, realm, ssl)
        self.session = Session(address)


    def call(self,
             method, *args,
             on_success = lambda: None,
             on_error = lambda: None,
             **kwargs):

        def on_connected(_):
            deferred = self.session.call(method, *args, **kwargs)
            deferred.addCallbacks(on_success, on_error)
            deferred.addBoth(self.shutdown)

        def connection_error(error):
            sys.stderr.write("Error connecting to Golem instance ({}): {}\n"
                             .format(self.session.address, error))

            self.shutdown()

        self.session.connect(
            auto_reconnect=False
        ).addCallbacks(on_connected, connection_error)

    def shutdown(self, *_):
        if self.session:
            self.session.disconnect()


def call_requestor(method, *args,
                   on_success=lambda x: print(x),
                   on_error=lambda: None,
                   **kwargs):

    client = RPCClient(host='localhost', port=REQUESTOR_RPC_PORT)
    client.call(method, *args,
                on_success=on_success,
                on_error=on_error,
                **kwargs)


def call_provider(method,
                  on_success=lambda x: print(x),
                  on_error=lambda: None,
                  *args, **kwargs):
    client = RPCClient(host='localhost', port=PROVIDER_RPC_PORT)
    client.call(method, *args,
                on_success=on_success,
                on_error=on_error,
                **kwargs)
