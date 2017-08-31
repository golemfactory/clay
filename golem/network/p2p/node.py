import logging
from typing import Optional, List
import rlp
from golem.core.simpleserializer import CBORSedes

from golem.core.hostaddress import \
    get_host_address, get_external_address, get_host_addresses
from golem.core.simpleserializer import DictSerializable

logger = logging.getLogger(__name__)

class Node(rlp.Serializable, DictSerializable):
    fields = [
        ('node_name', CBORSedes),
        ('key', CBORSedes),
        ('prv_addr', CBORSedes),
        ('prv_port', CBORSedes),
        ('pub_addr', CBORSedes),
        ('pub_port', CBORSedes),
        ('nat_type', CBORSedes),
        ('p2p_prv_port', CBORSedes),
        ('p2p_pub_port', CBORSedes),
        ('prv_addresses', rlp.sedes.CountableList(CBORSedes)),
        ('port_status', CBORSedes),
    ]

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
                 prv_addresses: Optional[List[str]] = None,
                 port_status: Optional[str] = None ) -> None:
    
       rlp.Serializable.__init__(self, node_name, key, prv_addr, prv_port, pub_addr, pub_port,
                 nat_type, p2p_prv_port, p2p_pub_port, prv_addresses, port_status)

    def collect_network_info(self, seed_host=None, use_ipv6=False):
        if not self.pub_addr:
            if self.prv_port:
                self.pub_addr, self.pub_port, self.nat_type = \
                    get_external_address(self.prv_port)
            else:
                self.pub_addr, _, self.nat_type = get_external_address()

        self.prv_addresses = get_host_addresses(use_ipv6)

        if not self.prv_addr:
            if self.pub_addr in self.prv_addresses:
                self.prv_addr = self.pub_addr
            else:
                self.prv_addr = get_host_address(seed_host, use_ipv6)

        if self.prv_addr not in self.prv_addresses:
            logger.warning("Specified node address {} is not among detected "
                           "network addresses: {}".format(self.prv_addr,
                                                          self.prv_addresses))

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
