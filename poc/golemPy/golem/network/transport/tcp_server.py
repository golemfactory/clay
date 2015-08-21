import logging

from server import Server
from tcp_network import TCPListeningInfo, TCPListenInfo

logger = logging.getLogger(__name__)


class TCPServer(Server):
    def __init__(self, config_desc, network):
        Server.__init__(self, config_desc, network)
        self.cur_port = 0

    def change_config(self, config_desc):
        Server.change_config(self, config_desc)
        if self.cur_port != 0:
            listening_info = TCPListeningInfo(self.cur_port, self._stopped_callback, self._stopped_errback)
            self.network.stop_listening(listening_info)

        self.start_accepting()

    def start_accepting(self):
        listen_info = TCPListenInfo(self.config_desc.startPort, self.config_desc.endPort,
                                    self._listening_established, self._listening_failure)
        self.network.listen(listen_info)

    def _stopped_callback(self):
        logger.debug("Stopped listening on previous port")

    def _stopped_errback(self):
        logger.debug("Failed to stop listening on previous port")

    def _listening_established(self, port):
        self.cur_port = port
        logger.info("Port {} opened - listening.".format(self.cur_port))

    def _listening_failure(self):
        logger.error("Listening on ports {} to {} failure.").format(self.config_desc.startPort,
                                                                    self.config_desc.endPort)

