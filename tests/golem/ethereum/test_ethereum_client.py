import logging

from ethereum.transactions import Transaction
from ethereum.utils import zpad

from golem.ethereum import Client
from golem.testutils import TempDirFixture
from golem.utils import encode_hex


class EthereumClientTest(TempDirFixture):
    def setUp(self):
        super(EthereumClientTest, self).setUp()
        # Show information about Ethereum node starting and terminating.
        logging.basicConfig(level=logging.INFO)
        self.client = Client(self.tempdir)

    def tearDown(self):
        self.client.node.stop()
        super(EthereumClientTest, self).tearDown()

    def test_client(self):
        client = self.client
        p = client.get_peer_count()
        assert type(p) is int
        s = client.is_syncing()
        assert type(s) is bool
        addr = b'FakeEthereumAddress!'
        assert len(addr) == 20
        hex_addr = encode_hex(addr)
        c = client.get_transaction_count(hex_addr)
        assert type(c) is int
        assert c == 0
        b = client.get_balance(hex_addr)
        assert b == 0

        # Patch web3.py to throw exception in getBalance.
        def raise_in_getBalance(addr, block):
            raise ValueError({'message': 'getBalance error!'})

        client.web3.eth.getBalance = raise_in_getBalance
        b = client.get_balance(hex_addr)
        assert b == 0

    def test_send_raw_transaction(self):
        client = self.client
        with self.assertRaises(ValueError):
            client.send("fake data")
        client.node.stop()

    def test_send_transaction(self):
        client = self.client
        addr = b'\xff' * 20
        priv = b'\xee' * 32
        tx = Transaction(1, 20 * 10**9, 21000, to=addr, value=0, data=b'')
        tx.sign(priv)
        with self.assertRaisesRegex(ValueError, "[Ii]nsufficient funds"):
            client.send(tx)

    def test_start_terminate(self):
        client = self.client
        assert client.node.is_running()
        client.node.stop()
        assert not client.node.is_running()
        client.node.start()
        assert client.node.is_running()
        client.node.stop()
        assert not client.node.is_running()

    def test_get_logs(self):
        addr = encode_hex(zpad(b'deadbeef', 32))
        log_id = encode_hex(zpad(b'beefbeef', 32))
        client = self.client
        logs = client.get_logs(from_block='latest', to_block='latest',
                               topics=[log_id, addr])
        assert logs == []

        # GG todo
        #self.processor._PaymentProcessor__client.web3._requestManager.provider.ipc_path = '/home/ggruszczynski/.ethereum/rinkeby/geth.ipc'
        client.web3._requestManager.provider.ipc_path = '/home/ggruszczynski/.ethereum/rinkeby/geth.ipc'
        # client.web3._requestManager.provider.ipc_path = '/tmp/rinkeby-49447'

        my_address = '0x000000000000000000000000aa4abfaaa535087386e9c5bc82b7c858224988bf'

        LOG_ID = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'  # noqa

        block_num = 753335
        block_hash ='0xa435eda52586183f1362dcebb42b3ccf15ee4e033d2420543fa5be1130644f27'

        # from time import sleep
        # syncing = True
        # while syncing:
        #     try:
        #         syncing = client.is_syncing()
        #         latest = client.web3.eth.getBlock('latest')
        #         print('latest block number:' + str(latest['number']))
        #     except Exception as e:
        #         syncing = False
        #     else:
        #         sleep(0.5)


        block_info = client.web3.eth.getBlock(block_hash)

        logs2 = client.get_logs(from_block=block_num,
                                to_block=block_num,
                                topics=[LOG_ID, None, my_address])


        assert logs2 != None


    def test_filters(self):
        """ Test creating filter and getting logs """
        client = self.client
        filter_id = client.new_filter()
        assert type(filter_id) is str
        # Filter id is hex encoded 256-bit integer.
        assert filter_id.startswith('0x')
        number = int(filter_id, 16)
        assert 0 < number < 2**256

        entries = client.get_filter_changes(filter_id)
        assert not entries
