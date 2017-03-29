import logging
import rlp
from golem.core.simpleserializer import CBORSedes

from golem.core.hostaddress import get_host_address, get_external_address, get_host_addresses

logger = logging.getLogger(__name__)

class Node(rlp.Serializable):
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
        ('prv_addresses', rlp.sedes.CountableList(CBORSedes))
    ]

    def __init__(self, node_name=None, key=None, prv_addr=None, prv_port=None, pub_addr=None, pub_port=None,
                 nat_type=None, p2p_prv_port=None, p2p_pub_port=None, prv_addresses=None):

        rlp.Serializable.__init__(self, node_name, key, prv_addr, prv_port, pub_addr, pub_port,
                 nat_type, p2p_prv_port, p2p_pub_port, prv_addresses)

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

    def __str__(self):
        return "Node {}, (key: {})".format(self.node_name, self.key)
