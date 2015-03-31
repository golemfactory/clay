import json
import requests

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

from golem.core.variables import CONTRACT_ID

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

