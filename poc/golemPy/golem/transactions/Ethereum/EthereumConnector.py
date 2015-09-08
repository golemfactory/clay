import json
import requests
import logging
from sha3 import sha3_256

from EthereumAbi import encode_abi

logger = logging.getLogger(__name__)

class EthJSON:
    def __init__(self):
        self.data = {"jsonrpc": "2.0", "params": [], "id": 1, "method": ""}

    def setMethod(self, method):
        self.data["method"] = method

    def getData(self):
        return self.data

    def setId(self, id):
        self.data["id"] = id

    def addParam(self, param):
        self.data["params"].append(param)

from golem.core.variables import CONTRACT_ID, PAY_HASH

class EthereumConnector:
    def __init__(self, url):
        self.url = url
        self.headers = {"content-type": "application/json"}

    def sendJsonRpc(self, data):
        return requests.post(self.url, data=json.dumps(data), headers=self.headers).json()

    def sendTransaction(self, id, gas, gasPrice, value, data, to = CONTRACT_ID,):
        dataDesc = EthJSON()
        param = {}
        param["from"] = id
        param["to"] = to
        param["gas"] = gas
        param["gasPrice"] = gasPrice
        param["value"] = value
        param["data"] = data
        dataDesc.addParam(param)
        dataDesc.setMethod("eth_sendTransaction")
        dataDesc.setId(1)
        return self.sendJsonRpc(dataDesc.getData())

    def uuidToLong(self, uuid):
        return int(sha3_256(str(uuid)).hexdigest(), 16)

    def payForTask(self, eth_account, task_id, payments):
        gas = "0x76c0"
        gasPrice = "0x9184e72a000"
        tranVal = 9000 + sum(payments.values())
        task_id = self.uuidToLong(task_id)
        values = payments.values()
        keys = payments.keys()
        addresses = [str(bytearray.fromhex(key[2:])) for key in keys]

        data = PAY_HASH
        data += encode_abi(['uint256', 'address[]', 'uint256[]'],  [task_id, addresses, values]).encode('hex')
        logger.debug("Transaction data {}".format(data))

        #self.sendTransaction(eth_account, gas, gasPrice, tranVal, data)

