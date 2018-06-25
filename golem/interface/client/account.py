from typing import Dict, Any
import getpass
import zxcvbn

from decimal import Decimal
from ethereum.utils import denoms

from golem.core.deferred import sync_wait
from golem.interface.command import Argument, command, group

MIN_LENGTH = 5
MIN_SCORE = 2


@group(help="Manage account")
class Account:
    client = None  # type: 'golem.rpc.session.Client'

    amount_arg = Argument('amount', help='Amount to withdraw, eg 1.45')
    address_arg = Argument('destination', help='Address to send the funds to')
    currency_arg = Argument('currency', help='ETH or GNT')

    @command(help="Display account & financial info")
    def info(self) -> Dict[str, Any]:  # pylint: disable=no-self-use
        client = Account.client

        node = sync_wait(client.get_node())
        node_key = node['key']

        computing_trust = sync_wait(client.get_computing_trust(node_key))
        requesting_trust = sync_wait(client.get_requesting_trust(node_key))
        payment_address = sync_wait(client.get_payment_address())

        balance = sync_wait(client.get_balance())
        if balance is None:
            balance = {
                'gnt': 0,
                'av_gnt': 0,
                'eth': 0,
                'gnt_lock': 0,
                'eth_lock': 0
            }

        gnt_balance = int(balance['gnt'])
        gnt_available = int(balance['av_gnt'])
        eth_balance = int(balance['eth'])
        gnt_reserved = gnt_balance - gnt_available
        gnt_locked = int(balance['gnt_lock'])
        eth_locked = int(balance['eth_lock'])

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
                eth_balance=_fmt(eth_balance, unit="ETH"),
                gnt_locked=_fmt(gnt_locked),
                eth_locked=_fmt(eth_locked, unit="ETH"),
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
            # Check password length
            if len(pswd) < MIN_LENGTH:
                return "Password is too short, minimum is 5"

            # Check password score, same library and settings used on electron
            account_name = getpass.getuser() or ''
            result = zxcvbn.zxcvbn(pswd, user_inputs=['Golem', account_name])
            # print(result['score'])
            if result['score'] < MIN_SCORE:
                return "Password is not strong enough. " \
                    "Please use capitals, numbers and special characters."

            # Confirm the password
            confirm = getpass.getpass('Confirm password:')
            if confirm != pswd:
                return "Password and confirmation do not match."
            print("Generating keys, this can take up to 10 minutes...")

        success = sync_wait(client.set_password(pswd), timeout=15 * 60)
        if not success:
            return "Incorrect password"

        return "Account unlock success"

    @command(
        arguments=(amount_arg, address_arg, currency_arg),
        help="Withdraw GNT/ETH")
    def withdraw(  # pylint: disable=no-self-use
            self,
            amount,
            destination,
            currency) -> str:
        amount = str(int(Decimal(amount) * denoms.ether))
        return sync_wait(Account.client.withdraw(amount, destination, currency))

    @command(help="Trigger graceful shutdown of your golem")
    def shutdown(self) -> str:  # pylint: disable=no-self-use

        result = sync_wait(Account.client.graceful_shutdown())

        return "Graceful shutdown triggered result: {}".format(result)


def _fmt(value: int, unit: str = "GNT") -> str:
    full = value // denoms.ether
    decimals = '.' + str(value % denoms.ether).zfill(18).rstrip('0')
    if decimals == '.':
        decimals = ''
    return "{}{} {}".format(full, decimals, unit)
