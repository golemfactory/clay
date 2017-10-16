
import json
from ethereum import abi

def translate_contract(cls, contract: str) -> abi.ContractTranslator:
    from golem.utils import get_raw_string

    transalted_contract = abi.ContractTranslator(
        json.loads(get_raw_string(contract)))
    return transalted_contract

class GolemContracts(object):
    """
    GolemContracts stores contracts abi and their addresses
    """
    from golem.utils import decode_hex
    from golem.ethereum.contracts import GNTW, Test_GNT_Faucet, GNT_Deposit, GNT

    tGNT_addr = decode_hex("34cB7577690e01A1C53597730e2e1112f72DBeB5")
    tGNT_Contract =  translate_contract(GNT.ABI)

    GNT_Deposit_addr = decode_hex("7047c04EB5337bf4fD7033B24d411D50b57feb5C")
    GNT_Deposit_Contract = translate_contract(GNT_Deposit.ABI)

    tGNT_Faucet_addr = decode_hex("37Ce6582eB657D46a4EB802538C02FE69b48a348")
    tGNT_Faucet_Contract = translate_contract(Test_GNT_Faucet.ABI)

    GNTW_addr = decode_hex("584d53B8C2D0d0d7e27815D8482df8c96a8CD32D")
    GNTW_Contract = translate_contract(GNTW.ABI)
