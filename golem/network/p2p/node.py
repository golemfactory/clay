import logging
from typing import Optional, List

from golem.core.hostaddress import get_host_address, get_external_address, get_host_addresses

logger = logging.getLogger(__name__)


class Node:
    def __init__(self,
                 node_name: Optional[str] = None,
                 key: Optional[str] = None,
                 prv_addr: Optional[str] = None,
                 prv_port: Optional[int] = None,
                 pub_addr: Optional[str] = None,
                 pub_port: Optional[int] = None,
                 nat_type: Optional[List[str]] = None,
                 p2p_prv_port: Optional[int] = None,
                 p2p_pub_port: Optional[int] = None) -> None:
        self.node_name = node_name
        self.key = key
        # task server ports
        self.prv_port = prv_port
        self.pub_port = pub_port
        # p2p server ports
        self.p2p_prv_port = p2p_prv_port
        self.p2p_pub_port = p2p_pub_port
        # addresses
        self.prv_addr = prv_addr
        self.pub_addr = pub_addr
        self.prv_addresses = []  # type: List[str]

        self.nat_type = nat_type
        self.port_status = None

    def collect_network_info(self, seed_host=None, use_ipv6=False):
        if not self.pub_addr:
            if self.prv_port:
                self.pub_addr, self.pub_port, self.nat_type = get_external_address(self.prv_port)
            else:
                self.pub_addr, _, self.nat_type = get_external_address()

        self.prv_addresses = get_host_addresses(use_ipv6)

        if not self.prv_addr:
            if self.pub_addr in self.prv_addresses:
                self.prv_addr = self.pub_addr
            else:
                self.prv_addr = get_host_address(seed_host, use_ipv6)

        if self.prv_addr not in self.prv_addresses:
            logger.warn("Specified node address {} is not among detected "
                        "network addresses: {}".format(self.prv_addr,
                                                       self.prv_addresses))

    def is_super_node(self):
        if self.pub_addr is None or self.prv_addr is None:
            return False
        return self.pub_addr == self.prv_addr

    def __str__(self) -> str:
        return "Node {}, (key: {})".format(self.node_name, self.key)

    def to_dict(self) -> dict:
        return self.__dict__

    @staticmethod
    def from_dict(d: dict) -> 'Node':
        n = Node()
        n.__dict__.update(d)
        return n
