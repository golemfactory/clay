import unittest

import sys
import os

sys.path.append( os.environ.get( 'GOLEM' ) )

from golem.transactions.EthereumConnector import EthereumConnector, EthJSON

sys.path.append( os.environ.get( 'GOLEM' ) )

address = "http://10.30.10.75:8080"

class TestEthereumConnector( unittest.TestCase ):
    def testSha3(self):
        dataDesc = EthJSON()
        dataDesc.setMethod("web3_sha3")
        dataDesc.setId(64)
        dataDesc.addParam( "0x68656c6c6f20776f726c64" )
        data = dataDesc.getData()
        ec = EthereumConnector(address)
        self.assertEqual( ec.sendJsonRpc(data), {"id":64, "jsonrpc":"2.0", "result":"0x47173285a8d7341e5e972fc677286384f802f8ef42a5ec5f03bbfa254cb01fad" })

if __name__ == '__main__':
    unittest.main()