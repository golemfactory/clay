import datetime
import getpass
import sys
from typing import (
    Any,
    Dict,
    TYPE_CHECKING,
)

from decimal import Decimal
from ethereum.utils import denoms
import zxcvbn

from golem.node import ShutdownResponse
from golem.core.deferred import sync_wait
from golem.interface.command import Argument, command, group

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from golem.rpc.session import ClientProxy

MIN_LENGTH = 5
MIN_SCORE = 2


@group(help="Manage account")
class Account:
    client: 'ClientProxy'

    amount_arg = Argument('amount', help='Amount to withdraw, eg 1.45')
    address_arg = Argument('destination', help='Address to send the funds to')
    currency_arg = Argument('currency', help='ETH or GNT')
    gas_price_arg = Argument(
        'gas_price',
        help='Gas price in wei (not gwei)',
        optional=True,
    )

    @command(help="Display account & financial info")
    def info(self) -> Dict[str, Any]:  # pylint: disable=no-self-use
        client = Account.client

        node = sync_wait(client.get_node())
        node_key = node['key']

        computing_trust = sync_wait(client.get_computing_trust(node_key))
        requesting_trust = sync_wait(client.get_requesting_trust(node_key))
        # pylint: disable=protected-access
        payment_address = sync_wait(client._call('pay.ident'))

        balance = sync_wait(client.get_balance())

        gnt_available = int(balance['av_gnt'])
        gnt_nonconverted = int(balance['gnt_nonconverted'])
        eth_balance = int(balance['eth'])
        gnt_locked = int(balance['gnt_lock'])
        eth_locked = int(balance['eth_lock'])

        deposit_balance = sync_wait(client.get_deposit_balance())

        return dict(
            node_name=node['node_name'],
            Golem_ID=node_key,
            requestor_reputation=int(requesting_trust * 100),
            provider_reputation=int(computing_trust * 100),
            finances=dict(
                eth_address=payment_address,
                eth_available=_fmt(eth_balance, unit="ETH"),
                eth_locked=_fmt(eth_locked, unit="ETH"),
                gnt_available=_fmt(gnt_available),
                gnt_locked=_fmt(gnt_locked),
                gnt_unadopted=_fmt(gnt_nonconverted),
                deposit_balance=_fmt_deposit(deposit_balance),
            )
        )

    @command(help="Unlock account, will prompt for your password")
    def unlock(self) -> str:  # pylint: disable=no-self-use
        from twisted.internet import threads
        client = Account.client

        is_account_unlocked: bool = sync_wait(client.is_account_unlocked())
        if is_account_unlocked:
            return "Account already unlocked"

        has_key = sync_wait(client.key_exists())

        if not has_key:
            print("No account found, generate one by setting a password")
        else:
            print("Unlock your account to start golem")

        print("This command will time out in 30 seconds.")

        defer_getpass = threads.deferToThread(getpass.getpass, 'Password:')

        # FIXME: Command does not exit on its own,
        # needs manual "Return" key or sys.exit()
        defer_getpass.addErrback(lambda _: sys.exit(1))

        pswd = sync_wait(defer_getpass, timeout=30)
        if not pswd:
            return "ERROR: No password provided"

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
        arguments=(address_arg, amount_arg, currency_arg, gas_price_arg),
        help=("Withdraw GNT/ETH\n"
              "(withdrawals are not available for the testnet)"))
    def withdraw(  # pylint: disable=no-self-use
            self,
            destination,
            amount,
            currency,
            gas_price) -> str:
        assert Account.client is not None
        amount = str(int(Decimal(amount) * denoms.ether))
        return sync_wait(Account.client.withdraw(
            amount,
            destination,
            currency,
            int(gas_price) if gas_price else None,
        ))

    @command(help="Trigger graceful shutdown of your golem")
    def shutdown(self) -> str:  # pylint: disable=no-self-use

        result = sync_wait(Account.client.graceful_shutdown())
        readable_result = repr(ShutdownResponse(result))

        return "Graceful shutdown triggered result: {}".format(readable_result)


def _fmt(value: int, unit: str = "GNT") -> str:
    full = value // denoms.ether
    decimals = '.' + str(value % denoms.ether).zfill(18).rstrip('0')
    if decimals == '.':
        decimals = ''
    return "{}{} {}".format(full, decimals, unit)


def _fmt_deposit(deposit_balance):
    if not deposit_balance:
        return None

    deposit_balance['value'] = _fmt(int(deposit_balance['value']))
    if deposit_balance['status'] == 'unlocking':
        locked_until = datetime.datetime.utcfromtimestamp(
            int(deposit_balance['timelock']),
        )
        delta = locked_until - datetime.datetime.utcnow()
        deposit_balance['timelock'] = str(delta)
    else:
        deposit_balance['timelock'] = None
    return deposit_balance
