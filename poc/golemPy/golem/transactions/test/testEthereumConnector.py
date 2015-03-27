import unittest

import sys
import os

sys.path.append( os.environ.get( 'GOLEM' ) )

from golem.transactions.EthereumConnector import EthereumConnector, EthJSON

sys.path.append( os.environ.get( 'GOLEM' ) )

address = "http://localhost:8080"

class TestEthereumConnector( unittest.TestCase ):
    def testSha3(self):
        dataDesc = EthJSON()
        dataDesc.setMethod("web3_sha3")
        dataDesc.setId(64)
        dataDesc.addParam( "0x68656c6c6f20776f726c64" )
        data = dataDesc.getData()
        ec = EthereumConnector(address)
        self.assertEqual( ec.sendJsonRpc(data), {"id":64, "jsonrpc":"2.0", "result":"0x47173285a8d7341e5e972fc677286384f802f8ef42a5ec5f03bbfa254cb01fad" })

    def testBlock(self):
        dataDesc = EthJSON()
        dataDesc.setMethod("eth_blockNumber")
        dataDesc.setId(83)
        data = dataDesc.getData()
        ec = EthereumConnector(address)
        self.assertGreater( int(ec.sendJsonRpc(data)["result"], 16), 30000)

    def testGetLogs(self):
        dataDesc = EthJSON()
        dataDesc.setMethod("eth_getLogs")
        dataDesc.setId(74)
       # dataDesc.addParam({"topics": ["0x12341234"]})b6d97503bff4edd93591c57fc91925b41a19bd9c
        data = dataDesc.getData()
        ec = EthereumConnector(address)
        print ec.sendJsonRpc(data)


if __name__ == '__main__':
    unittest.main()