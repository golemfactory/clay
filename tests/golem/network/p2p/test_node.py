import unittest
from golem.network.p2p.node import Node


def is_ip_address(address):
    """
    Check if @address is correct IP address
    :param address: Address to be checked
    :return: True if is correct, false otherwise
    """
    from ipaddress import ip_address, AddressValueError
    try:
        # will raise error in case of incorrect address
        ip_address(unicode(address))
        return True
    except (ValueError, AddressValueError):
        return False


class TestNode(unittest.TestCase):
    def test_str(self):
        n = Node(node_name="Blabla", key="ABC")
        self.assertNotIn("at", str(n))
        self.assertNotIn("at", "{}".format(n))
        self.assertIn("Blabla", str(n))
        self.assertIn("Blabla", "{}".format(n))
        self.assertIn("ABC", str(n))
        self.assertIn("ABC", "{}".format(n))

    def test_collect_network_info(self):
        """ Test configuring Node object """
        node = Node()
        node.collect_network_info()
        assert is_ip_address(node.pub_addr)
        assert is_ip_address(node.prv_addr)
        for address in node.prv_addresses:
            assert is_ip_address(address)
