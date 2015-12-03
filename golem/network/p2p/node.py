import rlp
from rlp.sedes import big_endian_int, binary, CountableList
from golem.core.hostaddress import get_host_address, get_external_address, get_host_addresses


class Node(rlp.Serializable):
    fields = (
        ('node_id', binary),
        ('key', binary),
        ('prv_addr', binary),
        ('prv_port', big_endian_int),
        ('pub_addr', binary),
        ('pub_port', big_endian_int),
        ('nat_type', binary),
        ('prv_addresses', CountableList(binary)),
    )

    def __init__(self, node_id='', key='', prv_addr='', prv_port=0,
                 pub_addr='', pub_port=0, nat_type='', prv_addresses=[]):
        # The constructor has to have exactly the same arguments as in fields.
        super(Node, self).__init__(node_id, key, prv_addr, prv_port, pub_addr,
                                   pub_port, nat_type, prv_addresses)

    def collect_network_info(self, seed_host=None, use_ipv6=False):
        self.prv_addr = get_host_address(seed_host, use_ipv6)
        if self.prv_port:
            self.pub_addr, self.pub_port, self.nat_type = get_external_address(self.prv_port)
        else:
            self.pub_addr, _, self.nat_type = get_external_address()
        self.prv_addresses = get_host_addresses(use_ipv6)

    def is_super_node(self):
        if self.pub_addr is None or self.prv_addr is None:
            return False
        return self.pub_addr == self.prv_addr
