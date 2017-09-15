import unittest
from golem.network.p2p.node import Node
import json


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

    def test_json(self) -> None:
        "Test serialization and deserialization"
        n = Node(node_name="Blabla", key="ABC")
        json_dict = n.to_dict()
        json_str = json.dumps(json_dict)
        print(json_str)
        deser_dict = json.loads(json_str)
        print(deser_dict)
        n_deser = Node.from_dict(deser_dict)
        self.assertEqual(n.__dict__, n_deser.__dict__)

    def test_get_addresses(self):
        prv_port = 1234
        prv_addresses = ['10.0.0.2', '192.168.0.7']
        pub_addr = '1.2.3.4'
        pub_port = 40041

        n = Node(prv_port=prv_port, prv_addresses=prv_addresses)

        res = n.get_addresses()
        self.assertEqual(2, len(res))
        for addr in prv_addresses:
            self.assertIn((addr, prv_port), res)

        n.pub_addr = pub_addr
        res = n.get_addresses()
        self.assertEqual(3, len(res))
        self.assertIn((pub_addr, prv_port), res)
        for addr in prv_addresses:
            self.assertIn((addr, prv_port), res)

        n.pub_port = pub_port
        res = n.get_addresses()
        self.assertEqual(3, len(res))
        self.assertIn((pub_addr, pub_port), res)
        for addr in prv_addresses:
            self.assertIn((addr, prv_port), res)
