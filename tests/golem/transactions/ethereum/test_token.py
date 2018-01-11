import json
import mock
import unittest
from os import urandom

from ethereum.utils import privtoaddr

from golem.ethereum.token import GNTToken, GNTWToken, encode_payments
from golem.utils import decode_hex, encode_hex


def mock_payment(value: int=1):
    p = mock.Mock()
    p.value = value
    p.payee = urandom(20)
    return p


class GNTTokenTest(unittest.TestCase):
    def setUp(self):
        self.client = mock.Mock()
        self.privkey = urandom(32)
        self.addr = '0x' + encode_hex(privtoaddr(self.privkey))
        self.token = GNTToken(self.client)

    def test_get_balance(self):
        abi = mock.Mock()
        self.token._GNTToken__testGNT = abi
        encoded_data = 'dada'
        abi.encode_function_call.return_value = encoded_data

        self.client.call.return_value = None
        self.assertEqual(None, self.token.get_balance(self.addr))
        abi.encode_function_call.assert_called_with(
            'balanceOf',
            [privtoaddr(self.privkey)])
        self.client.call.assert_called_with(
            _from=mock.ANY,
            to='0x' + encode_hex(self.token.TESTGNT_ADDR),
            data='0x' + encode_hex(encoded_data),
            block='pending')

        self.client.call.return_value = '0x'
        self.assertEqual(0, self.token.get_balance(self.addr))

        self.client.call.return_value = '0xf'
        self.assertEqual(15, self.token.get_balance(self.addr))

    def test_batches(self):
        p1 = mock_payment()
        p2 = mock_payment()
        p3 = mock_payment()

        nonce = 0
        self.client.get_transaction_count.return_value = nonce

        abi = mock.Mock()
        self.token._GNTToken__testGNT = abi
        encoded_data = 'dada'
        abi.encode_function_call.return_value = encoded_data

        tx = self.token.batch_transfer(self.privkey, [p1, p2, p3], 0)
        self.assertEqual(nonce, tx.nonce)
        self.assertEqual(self.token.TESTGNT_ADDR, tx.to)
        self.assertEqual(0, tx.value)
        expected_gas = self.token.GAS_BATCH_PAYMENT_BASE + \
            3 * self.token.GAS_PER_PAYMENT
        self.assertEqual(expected_gas, tx.startgas)
        self.assertEqual(encoded_data, tx.data)
        abi.encode_function_call.assert_called_with(
            'batchTransfer',
            [encode_payments([p1, p2, p3])])

    def test_get_incomes_from_block(self):
        block_number = 1
        receiver_address = '0xbadcode'
        some_address = '0xdeadbeef'

        self.client.get_logs.return_value = None
        incomes = self.token.get_incomes_from_block(block_number,
                                                    receiver_address)
        self.assertEqual(None, incomes)

        topics = [self.token.TRANSFER_EVENT_ID, None, receiver_address]
        self.client.get_logs.assert_called_with(
            block_number,
            block_number,
            '0x' + encode_hex(self.token.TESTGNT_ADDR),
            topics)

        self.client.get_logs.return_value = [{
            'topics': ['0x0', some_address, receiver_address],
            'data': '0xf',
        }]
        incomes = self.token.get_incomes_from_block(block_number,
                                                    receiver_address)
        self.assertEqual(1, len(incomes))
        self.assertEqual(some_address, incomes[0]['sender'])
        self.assertEqual(15, incomes[0]['value'])


def abi_encoder(function_name, args):
    def bytes2hex(elem):
        if isinstance(elem, bytes):
            return encode_hex(elem)
        if isinstance(elem, list):
            for i, e in enumerate(elem):
                elem[i] = bytes2hex(e)
        return elem

    args = bytes2hex(args.copy())
    res = json.dumps({'function_name': function_name, 'args': args})
    return res


class GNTWTokenTest(unittest.TestCase):
    def setUp(self):
        self.client = mock.Mock()
        self.privkey = urandom(32)
        self.addr = '0x' + encode_hex(privtoaddr(self.privkey))
        self.token = GNTWToken(self.client)

        gnt_abi = mock.Mock()
        gnt_abi.encode_function_call.side_effect = abi_encoder
        self.token._GNTWToken__gnt = gnt_abi

        gntw_abi = mock.Mock()
        gntw_abi.encode_function_call.side_effect = abi_encoder
        self.token._GNTWToken__gntw = gntw_abi

        self.balances = {
            'gnt': None,
            'gntw': None,
        }

        self.pda = bytearray(32)
        self.pda_create_called = False

        def client_call(_from, to, data, block):
            self.assertEqual('pending', block)
            token_addr = decode_hex(to)
            data = json.loads(decode_hex(data).decode())
            if data['function_name'] == 'balanceOf':
                self.assertEqual(1, len(data['args']))

                if privtoaddr(self.privkey) == decode_hex(data['args'][0]):
                    if token_addr == self.token.TESTGNT_ADDRESS:
                        return self.balances['gnt']
                    if token_addr == self.token.GNTW_ADDRESS:
                        return self.balances['gntw']

                raise Exception('Unknown balance')

            if data['function_name'] == 'getPersonalDepositAddress':
                self.assertEqual(self.token.GNTW_ADDRESS, token_addr)
                self.assertEqual(1, len(data['args']))
                self.assertEqual(
                    privtoaddr(self.privkey),
                    decode_hex(data['args'][0]))
                return '0x' + encode_hex(self.pda)

            raise Exception('Unknown call {}'.format(data['function_name']))

        self.nonce = 0
        self.process_deposit_called = False
        self.transfer_called = False

        def client_send(tx):
            token_addr = tx.to
            data = json.loads(tx.data)
            self.assertEqual(self.nonce, tx.nonce)
            self.nonce += 1
            if data['function_name'] == 'createPersonalDepositAddress':
                self.assertEqual(self.token.GNTW_ADDRESS, token_addr)
                self.assertEqual(0, len(data['args']))
                self.assertEqual(
                    self.token.CREATE_PERSONAL_DEPOSIT_GAS,
                    tx.startgas)
                self.pda_create_called = True
                return '0x' + encode_hex(urandom(32))

            if data['function_name'] == 'transfer':
                self.assertEqual(self.token.TESTGNT_ADDRESS, token_addr)
                self.assertEqual(2, len(data['args']))
                self.assertEqual(encode_hex(self.pda[-20:]), data['args'][0])
                self.assertEqual(int(self.balances['gnt'], 16), data['args'][1])
                self.transfer_called = True
                return '0x' + encode_hex(urandom(32))

            if data['function_name'] == 'processDeposit':
                self.assertEqual(self.token.GNTW_ADDRESS, token_addr)
                self.assertEqual(0, len(data['args']))
                self.process_deposit_called = True
                return '0x' + encode_hex(urandom(32))

            raise Exception('Unknown send {}'.format(data['function_name']))

        self.client.call.side_effect = client_call
        self.client.send.side_effect = client_send
        self.client.get_transaction_count.side_effect = lambda *_: self.nonce

    def test_get_balance(self):
        self.assertEqual(None, self.token.get_balance(self.addr))

        self.balances['gnt'] = '0x'
        self.assertEqual(None, self.token.get_balance(self.addr))

        self.balances['gntw'] = '0x'
        self.assertEqual(0, self.token.get_balance(self.addr))

        self.balances['gnt'] = '0xf'
        self.assertEqual(15, self.token.get_balance(self.addr))

        self.balances['gntw'] = '0xa'
        self.assertEqual(25, self.token.get_balance(self.addr))

    def test_batches_enough_gntw(self):
        p1 = mock_payment(1)
        p2 = mock_payment(2)
        p3 = mock_payment(3)

        self.balances['gnt'] = '0x0'
        self.balances['gntw'] = '0xf'

        closure_time = 0
        tx = self.token.batch_transfer(self.privkey, [p1, p2, p3], closure_time)
        self.assertEqual(self.nonce, tx.nonce)
        self.assertEqual(self.token.GNTW_ADDRESS, tx.to)
        self.assertEqual(0, tx.value)
        expected_gas = self.token.GAS_BATCH_PAYMENT_BASE + \
            3 * self.token.GAS_PER_PAYMENT
        self.assertEqual(expected_gas, tx.startgas)
        expected_data = abi_encoder(
            'batchTransfer',
            [encode_payments([p1, p2, p3]), closure_time])
        self.assertEqual(expected_data, tx.data)

    def test_batches_gnt_convertion(self):
        p1 = mock_payment()

        self.balances['gnt'] = '0x10'
        self.balances['gntw'] = '0x0'

        # Will need to convert GNT to GNTW
        closure_time = 0
        tx = self.token.batch_transfer(self.privkey, [p1], closure_time)
        self.assertEqual(None, tx)
        # Created personal deposit
        self.assertTrue(self.pda_create_called)
        self.pda_create_called = False
        # Waiting for personal deposit tx to be mined
        tx = self.token.batch_transfer(self.privkey, [p1], closure_time)
        self.assertEqual(None, tx)
        self.assertFalse(self.pda_create_called)
        self.assertFalse(self.transfer_called)
        self.assertFalse(self.process_deposit_called)
        # Personal deposit tx mined, sending and processing deposit
        self.pda = urandom(32)
        tx = self.token.batch_transfer(self.privkey, [p1], closure_time)
        self.assertEqual(None, tx)
        # 2 transactions to convert GNT to GNTW
        self.assertEqual(3, self.nonce)
        self.assertTrue(self.transfer_called)
        self.assertTrue(self.process_deposit_called)

    def test_get_incomes_from_block(self):
        block_number = 1
        receiver_address = '0xbadcode'
        some_address = '0xdeadbeef'

        self.client.get_logs.return_value = None
        incomes = self.token.get_incomes_from_block(block_number,
                                                    receiver_address)
        self.assertEqual(None, incomes)

        topics = [self.token.TRANSFER_EVENT_ID, None, receiver_address]
        self.client.get_logs.assert_called_with(
            block_number,
            block_number,
            '0x' + encode_hex(self.token.GNTW_ADDRESS),
            topics)

        self.client.get_logs.return_value = [{
            'topics': ['0x0', some_address, receiver_address],
            'data': '0xf',
        }]
        incomes = self.token.get_incomes_from_block(block_number,
                                                    receiver_address)
        self.assertEqual(1, len(incomes))
        self.assertEqual(some_address, incomes[0]['sender'])
        self.assertEqual(15, incomes[0]['value'])
