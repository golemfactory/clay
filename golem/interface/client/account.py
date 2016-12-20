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

    b, ab, deposit = wait(client.get_balance())
    b, ab, deposit = float(b), float(ab), float(deposit)
    rb = b - ab
    total = deposit + b

    return dict(
        node_name=node['node_name'],
        Golem_ID=node_key,
        requestor_reputation=int(requesting_trust * 100),
        provider_reputation=int(computing_trust * 100),
        finances=dict(
            eth_address=payment_address,
            local_balance=_fmt(b),
            total_balance=_fmt(total),
            available_balance=_fmt(ab),
            reserved_balance=_fmt(rb),
            deposit_balance=_fmt(deposit)
        )
    )


def _fmt(value):
    return "{:.6f} ETH".format(value / denoms.ether)
