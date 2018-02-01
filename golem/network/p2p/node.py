import logging
from typing import Optional, List

from golem.core.hostaddress import \
    get_host_address, get_external_address, get_host_addresses
from golem.core.simpleserializer import DictSerializable

logger = logging.getLogger(__name__)


class Node(DictSerializable):
    def __init__(self,
                 node_name: Optional[str] = None,
                 key: Optional[str] = None,
                 prv_addr: Optional[str] = None,
                 prv_port: Optional[int] = None,
                 pub_addr: Optional[str] = None,
                 pub_port: Optional[int] = None,
                 nat_type: Optional[List[str]] = None,
                 p2p_prv_port: Optional[int] = None,
                 p2p_pub_port: Optional[int] = None,
                 hyperdrive_prv_port: Optional[int] = None,
                 hyperdrive_pub_port: Optional[int] = None) -> None:

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
        # hyperdrive
        self.hyperdrive_prv_port = hyperdrive_prv_port
        self.hyperdrive_pub_port = hyperdrive_pub_port

        self.port_status = None

        self.nat_type = nat_type  # Please do not remove the nat_type property,
        # it's still useful for stats / debugging connectivity.

    def collect_network_info(self, seed_host=None, use_ipv6=False):
        self.prv_addresses = get_host_addresses(use_ipv6)

        if not self.pub_addr:
            self.pub_addr, _, self.nat_type = get_external_address()

        if not self.prv_addr:
            if self.pub_addr in self.prv_addresses:
                self.prv_addr = self.pub_addr
            else:
                self.prv_addr = get_host_address(seed_host, use_ipv6)

        if self.prv_addr not in self.prv_addresses:
            logger.warning("Specified node address {} is not among detected "
                           "network addresses: {}".format(self.prv_addr,
                                                          self.prv_addresses))

    def update_public_info(self) -> None:
        if self.pub_addr is None:
            self.pub_addr = self.prv_addr
        if self.pub_port is None:
            self.pub_port = self.prv_port
        if self.p2p_pub_port is None:
            self.p2p_pub_port = self.p2p_prv_port
        if self.hyperdrive_pub_port is None:
            self.hyperdrive_pub_port = self.hyperdrive_prv_port

    def is_super_node(self) -> bool:
        if self.pub_addr is None or self.prv_addr is None:
            return False
        return self.pub_addr == self.prv_addr

    def __str__(self) -> str:
        return "Node {}, (key: {})".format(self.node_name, self.key)

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @staticmethod
    def from_dict(data: Optional[dict]) -> 'Node':
        n = Node()
        if data:
            n.__dict__.update(data)
        return n

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Node):
            raise TypeError(
                "Mismatched types: expected Node, got {}".format(type(other))
            )
        return self.__dict__ == other.__dict__
