import unittest
from golem.transactions.ethereum.ethereumconnector import EthereumConnector, EthJSON

address = "http://localhost:8080"


class TestEthereumConnector(unittest.TestCase):

    @unittest.skip("Fix me (testing takes too long)")
    def testSha3(self):
        data_desc = EthJSON()
        data_desc.set_method("web3_sha3")
        data_desc.set_id(64)
        data_desc.add_param("0x68656c6c6f20776f726c64")
        data = data_desc.get_data()
        ec = EthereumConnector(address)
        self.assertEqual(ec.send_json_rpc(data), {"id": 64, "jsonrpc": "2.0",
                                                  "result": "0x47173285a8d7341e5e972fc677286384f802f8ef42a5ec5f03bbfa254cb01fad"})

    @unittest.skip("Fix me (testing takes too long)")
    def testBlock(self):
        data_desc = EthJSON()
        data_desc.set_method("eth_blockNumber")
        data_desc.set_id(83)
        data = data_desc.get_data()
        ec = EthereumConnector(address)
        self.assertGreater(int(ec.send_json_rpc(data)["result"], 16), 30000)

    @unittest.skip("Fix me (testing takes too long)")
    def testGetLogs(self):
        data_desc = EthJSON()
        data_desc.set_method("eth_getLogs")
        data_desc.set_id(74)
        data_desc.add_param({"topics": ["0x12341234"]})
        data = data_desc.get_data()
        ec = EthereumConnector(address)
        print ec.send_json_rpc(data)

    @unittest.skip("Fix me (testing takes too long)")
    def testSendTransaction(self):
        ec = EthereumConnector(address)
        self.assertNotIn(
            "error", ec.send_transaction(id="0xb60e8dd61c5d32be8058bb8eb970870f07233155",
                                         to="0xd46e8dd67c5d32be8058bb8eb970870f07244567",
                                         gas="0x76c0", gas_price="0x9184e72a000", value="0x9184e72a",
                                         data="0xd46e8dd67c5d32be8d46e8dd67c5d32be8058bb8eb970870f072445675058bb8eb970870f072445675"))
