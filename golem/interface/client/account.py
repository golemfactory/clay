from typing import Dict, Any
import getpass

from ethereum.utils import denoms

from golem.core.deferred import sync_wait
from golem.interface.command import command, group


@group(help="Manage account")
class Account:
    client = None  # type: 'golem.rpc.session.Client'

    @command(help="Display account & financial info")
    def info(self) -> Dict[str, Any]:  # pylint: disable=no-self-use
        client = Account.client

        node = sync_wait(client.get_node())
        node_key = node['key']

        computing_trust = sync_wait(client.get_computing_trust(node_key))
        requesting_trust = sync_wait(client.get_requesting_trust(node_key))
        payment_address = sync_wait(client.get_payment_address())

        balance = sync_wait(client.get_balance())
        if any(b is None for b in balance):
            balance = 0, 0, 0

        gnt_balance, gnt_available, eth_balance = balance[:3]
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

    @command(help="Unlock account, will prompt for your password")
    def unlock(self) -> str:  # pylint: disable=no-self-use
        client = Account.client
        has_key = sync_wait(client.key_exists())

        if not has_key:
            print("No account found, generate one by setting a password")
        else:
            print("Unlock your account to start golem")

        pswd = getpass.getpass('Password:')

        if not has_key:
            confirm = getpass.getpass('Confirm password:')
            if confirm != pswd:
                return "Password and confirmation do not match."
            print("Generating keys, this can take up to 10 minutes...")

        success = sync_wait(client.set_password(pswd), timeout=15 * 60)
        if not success:
            return "Incorrect password"

        return "Account unlock success"


def _fmt(value: float, unit: str = "GNT") -> str:
    return "{:.6f} {}".format(value / denoms.ether, unit)
