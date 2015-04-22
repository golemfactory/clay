import json
import requests
import logging

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
        self.data["params"].append( param )

from golem.core.variables import CONTRACT_ID, PAY_HASH

class EthereumConnector:
    def __init__(self, url):
        self.url = url
        self.headers = {"content-type": "application/json"}

    def sendJsonRpc(self, data):
        return requests.post(self.url, data=json.dumps(data), headers=self.headers).json()

    def sendTransaction(self, id, gas, gasPrice, value, data, to = CONTRACT_ID, ):
        dataDesc = EthJSON()
        param = {}
        param["from"] = id
        param["to"] = to
        param["gas"] = gas
        param["gasPrice"] = gasPrice
        param["value"] = value
        param["data"] = data
        dataDesc.addParam( param )
        dataDesc.setMethod("eth_sendTransaction")
        dataDesc.setId(1)
        return self.sendJsonRpc( dataDesc.getData())

    def payForTask( self, ethAccount, taskId, payments ):
        gas = "0x76c0"
        gasPrice =  "0x9184e72a000"
        tranVal = 9000
        addresses = []
        values = []
        if len(taskId) > 32:
            logger.warning("To long task, cropping...")
            taskId = taskId[:32]
        for ethAddr, val in payments.iteritems():
            addresses.append(ethAddr.zfill(32))
            values.append(str(val).zfill(32))
            val += tranVal
        data = PAY_HASH + taskId.zfill(32) + str(len(addresses)).zfill(32) + str(len(values)).zfill(32) + \
                "".join(addresses) + "".join(values)
        logger.debug("Transaction data {}".format(data))
        #Tymczasowo wykomentowane, zeby nie spalac etheru na prozno
       # self.sendTransaction(ethAccount, gas, gasPrice, hex(tranVal), data )

