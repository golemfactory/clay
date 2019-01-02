import logging

from golem_messages.datastructures import p2p as dt_p2p

from golem.core import hostaddress


logger = logging.getLogger(__name__)


class LocalNode(dt_p2p.Node):
    def collect_network_info(self, seed_host=None, use_ipv6=False):
        # pylint: disable=attribute-defined-outside-init
        # pylint: disable=access-member-before-definition
        self.prv_addresses = hostaddress.get_host_addresses(use_ipv6)

        if not self.pub_addr:
            self.pub_addr, _ = hostaddress.get_external_address()

        if not self.prv_addr:
            if self.pub_addr in self.prv_addresses:
                self.prv_addr = self.pub_addr
            else:
                self.prv_addr = hostaddress.get_host_address(
                    seed_host,
                    use_ipv6,
                )

        if self.prv_addr not in self.prv_addresses:
            logger.warning(
                "Specified node address %s is not among detected "
                "network addresses: %s",
                self.prv_addr,
                self.prv_addresses,
            )
