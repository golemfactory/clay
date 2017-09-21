from typing import Dict, Any

from autobahn.wamp.exception import ApplicationError

from ethereum.utils import denoms

from golem.core.deferred import sync_wait
from golem.interface.command import Argument, command, group
# For type annotations:
from golem.client import Client  # pylint: disable=unused-import


@group(help="Manage account")
class Account:
    # that's in fact golem.rpc.session.Client, which is created dynamically,
    # which is a subset of golem.client.Client
    # Anyway, we'll get better checks if we fool mypy to believe its the former
    client = None  # type: Client

    privkey = Argument(
        'privkey',
        help="The file the private key will be saved to"
    )
    pubkey = Argument(
        'pubkey',
        help="The file the public key will be saved to"
    )

    @command(help="Display account & financial info")
    def info(self) -> Dict[str, Any]:
        client = Account.client

        node = sync_wait(client.get_node())
        node_key = node['key']

        computing_trust = sync_wait(client.get_computing_trust(node_key))
        requesting_trust = sync_wait(client.get_requesting_trust(node_key))
        payment_address = sync_wait(client.get_payment_address())

        balance = sync_wait(client.get_balance())
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
                total_balance=_fmt(gnt_balance),
                available_balance=_fmt(gnt_available),
                reserved_balance=_fmt(gnt_reserved),
                eth_balance=_fmt(eth_balance, unit="ETH")
            )
        )

    @command(arguments=(privkey, pubkey), help="Export the keys")
    def export(self, pubkey: str, privkey: str) -> None:
        client = Account.client
        deferred = client.save_keys_to_files(
            private_key_path=privkey,
            public_key_path=pubkey
        )
        try:
            sync_wait(deferred)
        except ApplicationError as err:
            print("Saving the results failed: {}".format(err.args[1]))


def _fmt(value: float, unit: str = "GNT") -> str:
    return "{:.6f} {}".format(value / denoms.ether, unit)
