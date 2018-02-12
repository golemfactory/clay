import unittest
import unittest.mock as mock

from golem.ethereum.gntconverter import GNTConverter


class GNTConverterTest(unittest.TestCase):
    def setUp(self):
        self.sci = mock.Mock()
        self.sci.get_personal_deposit_slot.return_value = None
        self.converter = GNTConverter(self.sci)

    def test_flow(self):
        assert not self.converter.is_converting()

        receipts = {
        }
        self.sci.get_transaction_receipt.side_effect = \
            lambda tx_hash: receipts[tx_hash]
        block_number = 333
        self.sci.get_block_number.return_value = block_number
        gnt_amount = 123

        # create personal deposit slot
        cpds_tx_hash = '0xdead'
        self.sci.create_personal_deposit_slot.return_value = cpds_tx_hash
        self.converter.convert(gnt_amount)
        self.sci.get_personal_deposit_slot.assert_called_once_with()
        self.sci.create_personal_deposit_slot.assert_called_once_with()

        receipts[cpds_tx_hash] = {'blockNumber': block_number}
        assert self.converter.is_converting()
        self.sci.get_transaction_receipt.assert_called_once_with(cpds_tx_hash)
        self.sci.get_transaction_receipt.reset_mock()

        # create personal deposit slot mined, transfer GNT
        receipts[cpds_tx_hash] = {
            'blockNumber': block_number - GNTConverter.REQUIRED_CONFS,
            'status': '0x1',
        }
        pda = '0xdddd'
        self.sci.get_personal_deposit_slot.return_value = pda
        transfer_tx_hash = '0xbeef'
        self.sci.transfer_gnt.return_value = transfer_tx_hash
        self.sci.get_gnt_balance.return_value = 0
        assert self.converter.is_converting()
        self.sci.get_transaction_receipt.assert_called_once_with(cpds_tx_hash)
        self.sci.transfer_gnt.assert_called_once_with(pda, gnt_amount)
        self.sci.get_transaction_receipt.reset_mock()

        receipts[transfer_tx_hash] = {'blockNumber': block_number}
        assert self.converter.is_converting()
        self.sci.get_transaction_receipt.assert_called_once_with(
            transfer_tx_hash,
        )
        self.sci.get_transaction_receipt.reset_mock()

        # transfer GNT mined, process personal deposit
        receipts[transfer_tx_hash] = {
            'blockNumber': block_number - GNTConverter.REQUIRED_CONFS,
            'status': '0x1',
        }
        self.sci.get_gnt_balance.return_value = gnt_amount
        process_pd_tx_hash = '0xbad'
        self.sci.process_personal_deposit_slot.return_value = process_pd_tx_hash
        assert self.converter.is_converting()
        self.sci.get_transaction_receipt.assert_called_once_with(
            transfer_tx_hash,
        )
        self.sci.get_transaction_receipt.reset_mock()
        self.sci.process_personal_deposit_slot.assert_called_once_with()

        receipts[process_pd_tx_hash] = {'blockNumber': block_number}
        assert self.converter.is_converting()
        self.sci.get_transaction_receipt.assert_called_once_with(
            process_pd_tx_hash,
        )
        self.sci.get_transaction_receipt.reset_mock()

        # process personal deposit mined, conversion done
        receipts[process_pd_tx_hash] = {
            'blockNumber': block_number - GNTConverter.REQUIRED_CONFS,
            'status': '0x1',
        }
        assert not self.converter.is_converting()
        self.sci.get_transaction_receipt.assert_called_once_with(
            process_pd_tx_hash,
        )
        self.sci.get_transaction_receipt.reset_mock()
