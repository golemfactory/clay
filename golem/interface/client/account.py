from ethereum.utils import denoms
from decimal import Decimal

from golem.interface.command import command, CommandHelper


@command(help="Display account & financial info", root=True)
def account():

    wait = CommandHelper.wait_for
    client = account.client

    node = wait(account.client.get_node())
    node_key = node['key']

    computing_trust = wait(client.get_computing_trust(node_key))
    requesting_trust = wait(client.get_requesting_trust(node_key))
    payment_address = wait(client.get_payment_address())
    gnt_price, eth_price = wait(client.get_crypto_prices())
    gnt_price = deserialize(gnt_price)
    eth_price = deserialize(eth_price)

    balance = wait(client.get_balance())
    if any(b is None for b in balance):
        balance = 0, 0, 0

    gnt_balance, gnt_available, eth_balance = balance
    gnt_balance = float(gnt_balance)
    gnt_available = float(gnt_available)
    eth_balance = float(eth_balance)
    gnt_reserved = gnt_balance - gnt_available

    return dict(
        node_name=node['node_name'],
        Golem_ID=node_key,
        requestor_reputation=int(requesting_trust * 100),
        provider_reputation=int(computing_trust * 100),
        finances=dict(
            eth_address=payment_address,
            total_balance =_fmt(gnt_balance, gnt_price),
            available_balance =_fmt(gnt_available, gnt_price),
            reserved_balance =_fmt(gnt_reserved, gnt_price),
            eth_balance=_fmt(eth_balance, eth_price, unit="ETH")
        )
    )

def deserialize(mb_decimal):
    try:
        return float(Decimal(mb_decimal))
    except:
        return None


def _fmt(value, unit_price, unit="GNT"):
    value = value / denoms.ether
    if unit_price is not None:
        usd_price = value * unit_price
        return "{:.6f} {} ({:.2f} USD)".format(value, unit, usd_price)
    return "{:.6f} {} (? USD)".format(value, unit)
