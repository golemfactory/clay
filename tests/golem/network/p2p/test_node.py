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

    def test_update_public_info_invalid(self):
        node = Node(
            node_name="Node 1",
            key="key_1"
        )

        assert node.pub_addr is None
        assert node.pub_port is None
        assert node.p2p_pub_port is None
        assert node.hyperdrive_pub_port is None

        node.update_public_info()

        assert node.pub_addr is None
        assert node.pub_port is None
        assert node.p2p_pub_port is None
        assert node.hyperdrive_pub_port is None

    def test_update_public_info(self):
        node = Node(
            node_name="Node 1",
            key="key_1",
            prv_addr='10.0.0.10',
            prv_port=40103,
            p2p_prv_port=40102,
            hyperdrive_prv_port=3282
        )

        assert node.pub_addr is None
        assert node.pub_port is None
        assert node.p2p_pub_port is None
        assert node.hyperdrive_pub_port is None

        node.update_public_info()

        assert node.pub_addr == node.prv_addr
        assert node.pub_port == node.pub_port
        assert node.p2p_pub_port == node.p2p_pub_port
        assert node.hyperdrive_pub_port == node.hyperdrive_pub_port
