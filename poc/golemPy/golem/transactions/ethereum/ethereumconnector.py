import json
import requests
import logging
from sha3 import sha3_256

from golem.core.variables import CONTRACT_ID, PAY_HASH

from ethereum_abi import encode_abi

logger = logging.getLogger(__name__)


class EthJSON(object):
    """ Help to prepare data for Ethreum JSON-RPC operation """
    def __init__(self):
        """ Create new basic data"""
        self.data = {"jsonrpc": "2.0", "params": [], "id": 1, "method": ""}

    def set_method(self, method):
        self.data["method"] = method

    def get_data(self):
        return self.data

    def set_id(self, id_):
        self.data["id"] = id_

    def add_param(self, param):
        self.data["params"].append(param)


class EthereumConnector(object):
    """ Ethereum connector class """
    def __init__(self, url):
        """ Create new connector that will send JSON-RPC messages to a given url
        :param url: data will be send to this address
        """
        self.url = url
        self.headers = {"content-type": "application/json"}

    def send_json_rpc(self, data):
        """ Send given data as a json-rpc post message
        :param data: json data for ethereum
        :return Response: response to request
        """
        return requests.post(self.url, data=json.dumps(data), headers=self.headers).json()

    def send_transaction(self, id_, gas, gas_price, value, data, to=CONTRACT_ID,):
        """
        Send transaction message to Ethereum
        :param id_: send ethereum account address
        :param gas: amount of that should be bought
        :param gas_price: gas price
        :param value: transaction value
        :param data: transaction data
        :param to: transaction recipient, default: golem contract
        :return Response: send transaction response
        """
        data_desc = EthJSON()
        param = {"from": id_, "to": to, "gas": gas, "gas_price": gas_price, "value": value, "data": data}
        data_desc.add_param(param)
        data_desc.set_method("eth_sendTransaction")
        data_desc.set_id(1)
        return self.send_json_rpc(data_desc.get_data())

    @staticmethod
    def uuid_to_long(uuid):
        """ Translate uui to long """
        return int(sha3_256(str(uuid)).hexdigest(), 16)

    def pay_for_task(self, eth_account, task_id, payments):
        """ Translate payments list to Ethereum transaction and send it as a transaction
        :param eth_account: recipient ethreum address
        :param task_id: payments is for task with given id
        :param payments: dict of payments
        :return Response: send transaction response
        """
        gas = "0x76c0"
        gas_price = "0x9184e72a000"
        tran_val = 9000 + sum(payments.values())
        task_id = EthereumConnector.uuid_to_long(task_id)
        values = payments.values()
        keys = payments.keys()
        addresses = [str(bytearray.fromhex(key[2:])) for key in keys]

        data = PAY_HASH
        data += encode_abi(['uint256', 'address[]', 'uint256[]'],  [task_id, addresses, values]).encode('hex')
        logger.debug("Transaction data {}".format(data))

        # return self.send_transaction(eth_account, gas, gas_price, tran_val, data)

