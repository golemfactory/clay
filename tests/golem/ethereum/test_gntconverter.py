import unittest
import unittest.mock as mock

from golem.ethereum.gntconverter import GNTConverter


def mock_receipt(block_number: int):
    receipt = mock.Mock()
    receipt.status = 1
    receipt.block_number = block_number
    return receipt


class GNTConverterTest(unittest.TestCase):
    def setUp(self):
        self.sci = mock.Mock()
        self.sci.get_gate_address.return_value = None
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

        # open gate
        og_tx_hash = '0xdead'
        self.sci.open_gate.return_value = og_tx_hash
        self.converter.convert(gnt_amount)
        self.sci.get_gate_address.assert_called_once_with()
        self.sci.open_gate.assert_called_once_with()

        receipts[og_tx_hash] = mock_receipt(block_number)
        assert self.converter.is_converting()
        self.sci.get_transaction_receipt.assert_called_once_with(og_tx_hash)
        self.sci.get_transaction_receipt.reset_mock()

        # opening gate mined, transfer GNT
        receipts[og_tx_hash] = \
            mock_receipt(block_number - GNTConverter.REQUIRED_CONFS)
        pda = '0xdddd'
        self.sci.get_gate_address.return_value = pda
        transfer_tx_hash = '0xbeef'
        self.sci.transfer_gnt.return_value = transfer_tx_hash
        self.sci.get_gnt_balance.return_value = 0
        assert self.converter.is_converting()
        self.sci.get_transaction_receipt.assert_called_once_with(og_tx_hash)
        self.sci.transfer_gnt.assert_called_once_with(pda, gnt_amount)
        self.sci.get_transaction_receipt.reset_mock()

        receipts[transfer_tx_hash] = mock_receipt(block_number)
        assert self.converter.is_converting()
        self.sci.get_transaction_receipt.assert_called_once_with(
            transfer_tx_hash,
        )
        self.sci.get_transaction_receipt.reset_mock()

        # transfer GNT mined, transfer from gate
        receipts[transfer_tx_hash] = \
            mock_receipt(block_number - GNTConverter.REQUIRED_CONFS)
        self.sci.get_gnt_balance.return_value = gnt_amount
        process_pd_tx_hash = '0xbad'
        self.sci.transfer_from_gate.return_value = process_pd_tx_hash
        assert self.converter.is_converting()
        self.sci.get_transaction_receipt.assert_called_once_with(
            transfer_tx_hash,
        )
        self.sci.get_transaction_receipt.reset_mock()
        self.sci.transfer_from_gate.assert_called_once_with()

        receipts[process_pd_tx_hash] = mock_receipt(block_number)
        assert self.converter.is_converting()
        self.sci.get_transaction_receipt.assert_called_once_with(
            process_pd_tx_hash,
        )
        self.sci.get_transaction_receipt.reset_mock()

        # transfer_from_fate mined, conversion done
        receipts[process_pd_tx_hash] = \
            mock_receipt(block_number - GNTConverter.REQUIRED_CONFS)
        assert not self.converter.is_converting()
        self.sci.get_transaction_receipt.assert_called_once_with(
            process_pd_tx_hash,
        )
        self.sci.get_transaction_receipt.reset_mock()
