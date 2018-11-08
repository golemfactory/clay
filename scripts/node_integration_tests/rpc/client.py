import os
import sys

from golem.core.simpleenv import get_local_datadir
from golem.rpc.cert import CertificateManager, CertificateError
from golem.rpc.common import (
    CROSSBAR_REALM, CROSSBAR_PORT, CROSSBAR_HOST, CROSSBAR_DIR
)
from golem.rpc.session import Session, WebSocketAddress


from scripts.node_integration_tests.params import (
    REQUESTOR_RPC_PORT, PROVIDER_RPC_PORT, get_datadir
)


class RPCClient:

    def __init__(self,
                 datadir: str,
                 host: str = CROSSBAR_HOST,
                 port: int = CROSSBAR_PORT,
                 realm: str = CROSSBAR_REALM,
                 ssl: bool = True) -> None:

        address = WebSocketAddress(host, port, realm, ssl)
        cert_manager = CertificateManager(
            os.path.join(get_local_datadir(datadir), CROSSBAR_DIR)
        )
        crsb_user = cert_manager.CrossbarUsers.golemcli
        secret = cert_manager.get_secret(crsb_user)
        self.session = Session(
            address,
            crsb_user=crsb_user,
            crsb_user_secret=secret,
        )

    def call(self,
             method, *args,
             on_success=lambda: None,
             on_error=None,
             **kwargs):

        def on_connected(_):
            def default_errback(error):
                print("Error: {}".format(error))

            deferred = self.session.call(method, *args, **kwargs)
            deferred.addCallbacks(on_success, on_error or default_errback)
            deferred.addBoth(self.shutdown)

        def connection_error(error):
            sys.stderr.write("Error connecting to Golem instance ({}): {}\n"
                             .format(self.session.address, error))

            self.shutdown()

        return self.session.connect(
            auto_reconnect=False
        ).addCallbacks(on_connected, on_error or connection_error)

    def shutdown(self, *_):
        if self.session:
            self.session.disconnect()


def _call(method, *args, port, datadir, on_success, on_error, **kwargs):
    try:
        client = RPCClient(
            host='localhost',
            port=port,
            datadir=datadir,
        )
    except CertificateError as e:
        on_error(e)
        return

    return client.call(method, *args,
                on_success=on_success,
                on_error=on_error,
                **kwargs)


def call_requestor(method, *args,
                   on_success=lambda x: print(x),
                   on_error=lambda: None,
                   **kwargs):
    return _call(
        method,
        port=int(REQUESTOR_RPC_PORT),
        datadir=get_datadir('requestor'),
        *args,
        on_success=on_success,
        on_error=on_error,
        **kwargs,
    )


def call_provider(method, *args,
                  on_success=lambda x: print(x),
                  on_error=None,
                  **kwargs):
    return _call(
        method,
        port=int(PROVIDER_RPC_PORT),
        datadir=get_datadir('provider'),
        *args,
        on_success=on_success,
        on_error=on_error,
        **kwargs,
    )
