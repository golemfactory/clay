from devp2p import slogging
from devp2p.peer import Peer

log = slogging.get_logger('p2p.peer')


COMPUTATION_CAPABILITY = 'computation'


class GolemPeer(Peer):

    @property
    def capabilities(self):
        capabilities = super().capabilities
        if self.peermanager.computation_capability:
            capabilities += [(COMPUTATION_CAPABILITY, 1)]
        return capabilities

    @property
    def computation_capability(self):
        return bool(self.peermanager.computation_capability)

    def _run_ingress_message(self):
        """
        Introduces extra exception handling to the original
        _run_ingress_message method.

        :return: None
        """
        try:
            return super()._run_ingress_message()
        except (OSError, ConnectionError) as exc:
            log.error('Connection error: %s', exc)
        except AssertionError as exc:
            if exc.args and exc.args[0] == 'connection is closed':
                log.error('Connection with %r closed unexpectedly',
                          self.remote_pubkey)
            else:
                raise
        self.stop()

    _run = _run_ingress_message
