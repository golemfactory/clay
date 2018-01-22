import abc
import json
import logging
from typing import List, Any

from ethereum import abi, utils, keys
from ethereum.transactions import Transaction
from ethereum.utils import denoms

from golem.ethereum import Client
from golem.model import Payment
from golem.utils import decode_hex, encode_hex
from .contracts import TestGNT
from .contracts import gntw

logger = logging.getLogger("golem.token")


def encode_payments(payments: List[Payment]):
    paymap = {}
    for p in payments:
        if p.payee in paymap:
            paymap[p.payee] += p.value
        else:
            paymap[p.payee] = p.value

    args = []
    value = 0
    for to, v in paymap.items():
        max_value = 2 ** 96
        if v >= max_value:
            raise ValueError("v should be less than {}".format(max_value))
        value += v
        v = utils.zpad(utils.int_to_big_endian(v), 12)
        pair = v + to
        if len(pair) != 32:
            raise ValueError(
                "Incorrect pair length: {}. Should be 32".format(len(pair)))
        args.append(pair)
    return args


class AbstractToken(object, metaclass=abc.ABCMeta):
    """
    This is a common interface for token transactions. It hides whether we're
    using GNT or GNTW underneath.
    """

    # Gas price: 20 gwei, Homestead suggested gas price.
    GAS_PRICE = 20 * 10 ** 9

    # Total gas for a batchTransfer is BASE + len(payments) * PER_PAYMENT
    GAS_PER_PAYMENT = 30000
    # tx: 21000, balance substract: 5000, arithmetics < 800
    GAS_BATCH_PAYMENT_BASE = 21000 + 800 + 5000

    def __init__(self, client: Client):
        self._client = client

    def _create_transaction(self,
                            sender: str,
                            token_address,
                            data,
                            gas: int) -> Transaction:
        nonce = self._client.get_transaction_count(sender)
        tx = Transaction(nonce,
                         self.GAS_PRICE,
                         gas,
                         to=token_address,
                         value=0,
                         data=data)
        return tx

    def _send_transaction(self,
                          privkey: bytes,
                          token_address: bytes,
                          data,
                          gas: int) -> Transaction:
        tx = self._create_transaction(
            '0x' + encode_hex(keys.privtoaddr(privkey)),
            token_address,
            data,
            gas)
        tx.sign(privkey)
        self._client.send(tx)
        return tx

    def _get_balance(self, token_abi, token_address: bytes, addr: str) -> int:
        data = token_abi.encode_function_call('balanceOf', [decode_hex(addr)])
        r = self._client.call(
            _from=addr,
            to='0x' + encode_hex(token_address),
            data='0x' + encode_hex(data),
            block='pending')
        if r is None:
            return None
        return 0 if r == '0x' else int(r, 16)

    def _request_from_faucet(self,
                             token_abi,
                             token_address: bytes,
                             privkey: bytes) -> None:
        data = token_abi.encode_function_call('create', [])
        self._send_transaction(privkey, token_address, data, 90000)

    def wait_until_synchronized(self) -> bool:
        return self._client.wait_until_synchronized()

    def is_synchronized(self) -> bool:
        return self._client.is_synchronized()

    @abc.abstractmethod
    def get_balance(self, addr: str) -> int:
        pass

    @abc.abstractmethod
    def batch_transfer(self,
                       privkey: bytes,
                       payments: List[Payment],
                       closure_time: int) -> Transaction:
        """
        Takes a list of payments to be made and returns prepared transaction
        for the batch payment. The transaction is not sent, but it is signed.
        It may return None when it's unable to make transaction at the moment,
        but this shouldn't be treated as an error. In case of GNTW sometimes
        we need to do some preparations (like convertion from GNT) before
        we can make a batch transfer.
        """
        pass

    @abc.abstractmethod
    def get_incomes_from_block(self, block: int, address) -> List[Any]:
        pass


class GNTToken(AbstractToken):
    """
    When the main token and the batchTransfer function are in the same contract.
    Which is the case for tGNT in testnet and eventually (after migration)
    will be the case for the new GNT in the mainnet as well.
    """
    TESTGNT_ADDR = decode_hex("7295bB8709EC1C22b758A8119A4214fFEd016323")

    # keccak256(Transfer(address,address,uint256))
    TRANSFER_EVENT_ID = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'  # noqa

    def __init__(self, client: Client):
        super().__init__(client)
        self.__testGNT = abi.ContractTranslator(json.loads(TestGNT.ABI))

    def get_balance(self, addr: str) -> int:
        balance = self._get_balance(
            self.__testGNT,
            self.TESTGNT_ADDR,
            addr)
        if balance is not None:
            logger.info("TestGNT: {}".format(balance / denoms.ether))
        return balance

    def request_from_faucet(self, privkey: bytes) -> None:
        self._request_from_faucet(self.__testGNT, self.TESTGNT_ADDR, privkey)

    def batch_transfer(self,
                       privkey: bytes,
                       payments: List[Payment],
                       closure_time: int) -> Transaction:
        p = encode_payments(payments)
        data = self.__testGNT.encode_function_call('batchTransfer', [p])
        gas = self.GAS_BATCH_PAYMENT_BASE + len(p) * self.GAS_PER_PAYMENT
        tx = self._create_transaction(
            '0x' + encode_hex(keys.privtoaddr(privkey)),
            self.TESTGNT_ADDR,
            data,
            gas)
        tx.sign(privkey)
        return tx

    def get_incomes_from_block(self, block: int, address: str) -> List[Any]:
        logs = self._client.get_logs(block,
                                     block,
                                     '0x' + encode_hex(self.TESTGNT_ADDR),
                                     [self.TRANSFER_EVENT_ID, None, address])
        if not logs:
            return logs

        res = []
        for entry in logs:
            if entry['topics'][2] != address:
                raise Exception("Unexpected income event from {}"
                                .format(entry['topics'][2]))

            res.append({
                'sender': entry['topics'][1],
                'value': int(entry['data'], 16),
            })
        return res


class GNTWToken(AbstractToken):
    """
    When batchTransfer function is in a different contract than the main token.
    GNTW implementation specifically.
    """
    GNTW_ADDRESS = decode_hex("a8CD649dB30b963592D88FdE95fe6284d6224329")
    TESTGNT_ADDRESS = decode_hex("2928aA793B79FCdb7b5B94f5d8419e0EE20AbDaF")
    FAUCET_ADDRESS = decode_hex("36FeE1616A131E7382922475A1BA67F88F891f0d")

    # keccak256(BatchTransfer(address,address,uint256,uint64))
    TRANSFER_EVENT_ID = '0x24310ec9df46c171fe9c6d6fe25cac6781e7fa8f153f8f72ce63037a4b38c4b6'  # noqa

    CREATE_PERSONAL_DEPOSIT_GAS = 320000
    PROCESS_DEPOSIT_GAS = 110000
    GNT_TRANSFER_GAS = 55000

    def __init__(self, client: Client):
        super().__init__(client)
        self.__gntw = abi.ContractTranslator(
            json.loads(gntw.GolemNetworkTokenWrapped.ABI))
        self.__gnt = abi.ContractTranslator(
            json.loads(gntw.GolemNetworkToken.ABI))
        self.__faucet = abi.ContractTranslator(json.loads(gntw.Faucet.ABI))
        self.__deposit_address = None
        self.__deposit_address_created = False
        self.__process_deposit_tx = None

    def get_balance(self, addr: str) -> int:
        gnt_balance = self._get_balance(self.__gnt, self.TESTGNT_ADDRESS, addr)
        if gnt_balance is None:
            return None

        gntw_balance = self._get_balance(self.__gntw, self.GNTW_ADDRESS, addr)
        if gntw_balance is None:
            return None

        logger.info("TestGNT: {} GNTW: {}".format(
            gnt_balance / denoms.ether,
            gntw_balance / denoms.ether))
        return gnt_balance + gntw_balance

    def request_from_faucet(self, privkey: bytes) -> None:
        self._request_from_faucet(self.__faucet, self.FAUCET_ADDRESS, privkey)

    def batch_transfer(self,
                       privkey: bytes,
                       payments: List[Payment],
                       closure_time: int) -> Transaction:
        if self.__process_deposit_tx:
            hstr = '0x' + encode_hex(self.__process_deposit_tx)
            receipt = self._client.get_transaction_receipt(hstr)
            if not receipt:
                logger.info("Waiting to process deposit")
                return None
            self.__process_deposit_tx = None

        addr = '0x' + encode_hex(keys.privtoaddr(privkey))
        gntw_balance = self._get_balance(self.__gntw, self.GNTW_ADDRESS, addr)
        if gntw_balance is None:
            return None
        total_value = sum([p.value for p in payments])
        if gntw_balance < total_value:
            logger.info("Not enough GNTW, trying to convert GNT. "
                        "GNTW: {}, total_value: {}"
                        .format(gntw_balance, total_value))
            self.__convert_gnt(privkey)
            return None

        p = encode_payments(payments)
        data = self.__gntw.encode_function_call('batchTransfer',
                                                [p, closure_time])
        gas = self.GAS_BATCH_PAYMENT_BASE + len(p) * self.GAS_PER_PAYMENT
        return self._create_transaction(addr, self.GNTW_ADDRESS, data, gas)

    def get_incomes_from_block(self, block: int, address: str) -> List[Any]:
        logs = self._client.get_logs(block,
                                     block,
                                     '0x' + encode_hex(self.GNTW_ADDRESS),
                                     [self.TRANSFER_EVENT_ID, None, address])
        if not logs:
            return logs

        res = []
        for entry in logs:
            if entry['topics'][2] != address:
                raise Exception("Unexpected income event from {}"
                                .format(entry['topics'][2]))

            res.append({
                'sender': entry['topics'][1],
                'value': int(entry['data'][:66], 16),
            })
        return res

    def __get_deposit_address(self, privkey: bytes) -> bytes:
        if not self.__deposit_address:
            addr_raw = keys.privtoaddr(privkey)
            data = self.__gntw.encode_function_call(
                'getPersonalDepositAddress',
                [addr_raw])
            res = self._client.call(_from='0x' + encode_hex(addr_raw),
                                    to='0x' + encode_hex(self.GNTW_ADDRESS),
                                    data='0x' + encode_hex(data),
                                    block='pending')
            if int(res, 16) != 0:
                self.__deposit_address = decode_hex(res)[-20:]
            elif not self.__deposit_address_created:
                data = self.__gntw.encode_function_call(
                    'createPersonalDepositAddress',
                    [])
                tx = self._send_transaction(privkey,
                                            self.GNTW_ADDRESS,
                                            data,
                                            self.CREATE_PERSONAL_DEPOSIT_GAS)
                logger.info("Create personal deposit address tx: {}"
                            .format(encode_hex(tx.hash)))
                self.__deposit_address_created = True
        return self.__deposit_address

    def __convert_gnt(self, privkey: bytes) -> None:
        gnt_balance = self._get_balance(
            self.__gnt,
            self.TESTGNT_ADDRESS,
            '0x' + encode_hex(keys.privtoaddr(privkey)))
        if gnt_balance is None:
            return

        logger.info("Converting {} GNT to GNTW".format(gnt_balance))
        pda = self.__get_deposit_address(privkey)
        if not pda:
            logger.info("Not converting until deposit address is known")
            return

        data = self.__gnt.encode_function_call(
            'transfer',
            [self.__deposit_address, gnt_balance])
        tx = self._send_transaction(privkey,
                                    self.TESTGNT_ADDRESS,
                                    data,
                                    self.GNT_TRANSFER_GAS)
        logger.info("Transfer GNT to personal deposit tx: {}"
                    .format(encode_hex(tx.hash)))

        data = self.__gntw.encode_function_call('processDeposit', [])
        tx = self._send_transaction(privkey,
                                    self.GNTW_ADDRESS,
                                    data,
                                    self.PROCESS_DEPOSIT_GAS)
        self.__process_deposit_tx = tx.hash
        logger.info("Process deposit tx: {}".format(encode_hex(tx.hash)))
