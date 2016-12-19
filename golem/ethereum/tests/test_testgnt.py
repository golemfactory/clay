from os import urandom


def test_balance0(chain):
    gnt = chain.get_contract('TestGNT')

    b = gnt.call().balanceOf('0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
    assert b == 0


def test_create(chain, accounts):
    gnt = chain.get_contract('TestGNT')

    assert gnt.call().totalSupply() == 0
    tx = gnt.transact({'gas': 100000}).create()
    chain.wait.for_receipt(tx)
    assert gnt.call().balanceOf(accounts[0]) == 1000 * 10**18
    assert gnt.call().totalSupply() == 1000 * 10**18


def test_transfer(chain):
    gnt = chain.get_contract('TestGNT')
    gnt.transact().create()
    addr = '0x' + urandom(20).encode('hex')
    value = 999 * 10**18
    tx = gnt.transact().transfer(addr, value)
    chain.wait.for_receipt(tx)
    assert gnt.call().balanceOf(addr) == value
