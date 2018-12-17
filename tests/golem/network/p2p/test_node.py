import unittest

from golem.network.p2p.local_node import LocalNode


def is_ip_address(address):
    """
    Check if @address is correct IP address
    :param address: Address to be checked
    :return: True if is correct, false otherwise
    """
    from ipaddress import ip_address, AddressValueError
    try:
        # will raise error in case of incorrect address
        ip_address(str(address))
        return True
    except (ValueError, AddressValueError):
        return False

class TestLocalNode(unittest.TestCase):
    def test_collect_network_info(self):
        """ Test configuring Node object """
        node = LocalNode(node_name="Saenchai Sor. Kingstar")
        node.collect_network_info()
        self.assertTrue(is_ip_address(node.pub_addr))
        self.assertTrue(is_ip_address(node.prv_addr))
        for address in node.prv_addresses:
            self.assertTrue(is_ip_address(address))
