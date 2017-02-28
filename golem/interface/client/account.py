from ethereum.utils import denoms

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

    gnt_balance, gnt_available, eth_balance = wait(client.get_balance())
    gnt_balance= float(gnt_balance)
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
            total_balance =_fmt(gnt_balance),
            available_balance =_fmt(gnt_available),
            reserved_balance =_fmt(gnt_reserved),
            eth_balance=_fmt(eth_balance, unit="ETH")
        )
    )


def _fmt(value, unit="GNT"):
    return "{:.6f} {}".format(value / denoms.ether, unit)
