from ipaddress import AddressValueError

import click

from golem.core.common import to_unicode
from golem.network.socketaddress import SocketAddress


def parse_node_addr(ctx, param, value):
    del ctx, param
    if value:
        try:
            SocketAddress(value, 1)
            return value
        except AddressValueError as e:
            raise click.BadParameter(
                "Invalid network address specified: {}".format(e))
    return ''


def parse_rpc_address(ctx, param, value):
    del ctx, param
    value = to_unicode(value)
    if value:
        try:
            return SocketAddress.parse(value)
        except AddressValueError as e:
            raise click.BadParameter(
                "Invalid RPC address specified: {}".format(e))


def parse_peer(ctx, param, value):
    del ctx, param
    addresses = []
    for arg in value:
        try:
            node_id, sock_addr = arg.split('@', 1)
            addresses.append([SocketAddress.parse(sock_addr), node_id])
        except (AddressValueError, ValueError) as e:
            raise click.BadParameter(
                "Invalid peer address specified: {}".format(e))
    return addresses
