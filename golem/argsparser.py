import ipaddress

import click

from golem.core.common import to_unicode
from golem.network.transport.tcpnetwork import SocketAddress


def enforce_start_geth_used(ctx, param, value):
    del param
    if value and not ctx.params.get('start_geth', False):
        raise click.BadParameter(
            "it makes sense only together with --start-geth")
    return value


def parse_http_addr(ctx, param, value):
    del ctx, param
    if value:
        try:
            http_prefix = 'http://'
            if not value.startswith(http_prefix):
                raise click.BadParameter(
                    "Address without http:// prefix"
                    "specified: {}".format(value))
            SocketAddress.parse(value[len(http_prefix):])
            return value
        except ipaddress.AddressValueError as e:
            raise click.BadParameter(
                "Invalid network address specified: {}".format(e))
    return None


def parse_node_addr(ctx, param, value):
    del ctx, param
    if value:
        try:
            SocketAddress(value, 1)
            return value
        except ipaddress.AddressValueError as e:
            raise click.BadParameter(
                "Invalid network address specified: {}".format(e))
    return None


def parse_rpc_address(ctx, param, value):
    del ctx, param
    value = to_unicode(value)
    if value:
        try:
            return SocketAddress.parse(value)
        except ipaddress.AddressValueError as e:
            raise click.BadParameter(
                "Invalid RPC address specified: {}".format(e))
    return None


def parse_peer(ctx, param, value):
    del ctx, param
    addresses = []
    for arg in value:
        try:
            addresses.append(SocketAddress.parse(arg))
        except ipaddress.AddressValueError as e:
            raise click.BadParameter(
                "Invalid peer address specified: {}".format(e))
    return addresses


def parse_port(ctx, param, value):
    del ctx, param
    if value is not None:
        try:
            if not 0 < int(value) < 65536:
                raise Exception('{} is not in range (1-65535)'.format(value))
        except Exception as e:  # pylint: disable=broad-except
            raise click.BadParameter('Invalid port: {}'.format(e))
    return value
