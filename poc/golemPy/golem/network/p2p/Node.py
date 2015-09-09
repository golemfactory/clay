from golem.core.hostaddress import get_host_address, get_external_address, get_host_addresses

##########################################################
class Node:
    #############################
    def __init__(self, node_id=None, key=None, prv_addr=None, prv_port=None, pub_addr=None, pub_port=None, nat_type=None):
        self.node_id = node_id
        self.key = key
        self.prv_addr = prv_addr
        self.prv_port = prv_port
        self.pub_addr = pub_addr
        self.pub_port = pub_port
        self.nat_type = nat_type
        self.prv_addresses = []

    #############################
    def collect_network_info(self, seed_host=None, use_ipv6=False):
        self.prv_addr = get_host_address(seed_host, use_ipv6)
        if self.prv_port:
            self.pub_addr, self.pub_port, self.nat_type = get_external_address(self.prv_port)
        else:
            self.pub_addr, _, self.nat_type = get_external_address()
        self.prv_addresses = get_host_addresses(use_ipv6)

    #############################
    def is_super_node(self):
        if self.pub_addr is None or self.prv_addr is None:
            return False
        return self.pub_addr == self.prv_addr

