
import json
from ethereum import abi

def translate_contract(contract: str) -> abi.ContractTranslator:
    from golem.utils import get_raw_string

    transalted_contract = abi.ContractTranslator(
        json.loads(get_raw_string(contract)))
    return transalted_contract

class GolemContracts(object):
    """
    GolemContracts stores contracts abi and their addresses
    """

    from golem.utils import decode_hex
    from golem.ethereum.contracts import \
        GNTW as __GNTW, \
        GNT_Faucet as __GNT_Faucet, \
        GNT_Deposit as __GNT_Deposit,\
        GNT as __GNT

    tGNT_addr = decode_hex("2928aa793b79fcdb7b5b94f5d8419e0ee20abdaf")
    tGNT_Contract =  translate_contract(__GNT.ABI)

    GNT_Deposit_addr = decode_hex("ceeb2a92ab5cc9c48acd0d656f7d0c6f0670a0d1")
    GNT_Deposit_Contract = translate_contract(__GNT_Deposit.ABI)

    tGNT_Faucet_addr = decode_hex("36fee1616a131e7382922475a1ba67f88f891f0d")
    tGNT_Faucet_Contract = translate_contract(__GNT_Faucet.ABI)

    GNTW_addr = decode_hex("a8cd649db30b963592d88fde95fe6284d6224329")
    GNTW_Contract = translate_contract(__GNTW.ABI)
