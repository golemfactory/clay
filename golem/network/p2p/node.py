import logging
import rlp
from golem.core.simpleserializer import CBORSerializer
from rlp.exceptions import ObjectSerializationError, ListSerializationError

from golem.core.hostaddress import get_host_address, get_external_address, get_host_addresses

logger = logging.getLogger(__name__)

class CBOR(rlp.Serializable):

    def __init__(self):
        rlp.Serializable.__init__(self)

    @classmethod
    def serialize(cls, obj):
        return CBORSerializer.dumps(obj)


    @classmethod
    def deserialize(cls, serial, exclude=None, **kwargs):
        return CBORSerializer.loads(serial)

class Node(rlp.Serializable):
    fields = (
        ('node_name', CBOR),
        ('key', CBOR),
        ('prv_addr', CBOR),
        ('prv_port', CBOR),
        ('pub_addr', CBOR),
        ('pub_port', CBOR),
        ('nat_type', CBOR),
        ('p2p_prv_port', CBOR),
        ('p2p_pub_port', CBOR),
        ('prv_addresses', rlp.sedes.CountableList(CBOR))
    )

    def __init__(self, node_name=None, key=None, prv_addr=None, prv_port=None, pub_addr=None, pub_port=None,
                 nat_type=None, p2p_prv_port=10, p2p_pub_port=None, prv_addresses=None):

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
