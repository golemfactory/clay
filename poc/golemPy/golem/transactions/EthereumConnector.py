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

class EthereumConnector:
    def __init__(self, url):
        self.url = url
        self.headers = {"content-type": "application/json"}

    def sendJsonRpc(self, data):
        return requests.post(self.url, data=json.dumps(data), headers=self.headers).json()
