import logging

from ethereum.utils import denoms

log = logging.getLogger("golem.gnt_converter")


class GNTConverter:
    REQUIRED_CONFS = 2

    def __init__(self, sci):
        self._sci = sci
        self._deposit_address = None
        self._tx_hash = None
        self._amount_to_convert = None

    def convert(self, amount: int):
        if self.is_converting():
            # This isn't a technical restriction but rather a simplification
            # for our use case
            raise Exception('Can process only single conversion at once')

        self._amount_to_convert = amount
        self._update_personal_deposit_address()

    def is_converting(self):
        if self._awaiting_transaction():
            return True

        if not self._amount_to_convert:
            return False

        if self._update_personal_deposit_address():
            return True

        if self._sci.get_gnt_balance(self._deposit_address):
            self._tx_hash = self._sci.process_personal_deposit_slot()
            self._amount_to_convert = None
            log.info('Processing personal deposit slot %r', self._tx_hash)
            return True

        self._tx_hash = self._sci.transfer_gnt(
            self._deposit_address,
            self._amount_to_convert,
        )
        log.info(
            'Converting %r GNT %r',
            self._amount_to_convert / denoms.ether,
            self._tx_hash,
        )

        return True

    def _update_personal_deposit_address(self) -> bool:
        if self._deposit_address is not None:
            return False

        self._deposit_address = self._sci.get_personal_deposit_slot()
        if self._deposit_address and int(self._deposit_address, 16) == 0:
            self._deposit_address = None

        if self._deposit_address is None:
            self._tx_hash = self._sci.create_personal_deposit_slot()
            log.info('Creating personal deposit slot %r', self._tx_hash)
            return True
        return False

    def _awaiting_transaction(self) -> bool:
        if self._tx_hash is None:
            return False
        receipt = self._sci.get_transaction_receipt(self._tx_hash)
        if not receipt:
            return True

        current_block = self._sci.get_block_number()
        block_number = receipt['blockNumber']
        if current_block < block_number + self.REQUIRED_CONFS:
            return True
        if receipt['status'] == '0x0':
            log.warning('Unsuccessful transaction %r', self._tx_hash)
        self._tx_hash = None
        return False
