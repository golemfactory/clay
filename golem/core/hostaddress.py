import logging
import netifaces

import os
import socket

import ipaddress
import stun

from variables import DEFAULT_CONNECT_TO, DEFAULT_CONNECT_TO_PORT

logger = logging.getLogger(__name__)

# Old method that works on Windows, but not on Linux (usually returns only 127.0.0.1)
# def ip4_addresses():
#   return [i[4][0] for i in socket.getaddrinfo(socket.gethostname(), 0, socket.AF_INET)]


def ip_addresses(use_ipv6=False):
    """ Return list of internet addresses that this host have
    :param bool use_ipv6: *Default: False* if True it returns this host IPv6 addresses, otherwise IPv4 addresses are
     returned
     :return list: list of host addresses
    """
    if use_ipv6:
        addr_family = netifaces.AF_INET6
    else:
        addr_family = netifaces.AF_INET
    addresses = []
    for inter in netifaces.interfaces():
        ip = netifaces.ifaddresses(inter).get(addr_family)
        if ip is None:
            continue
        for addrInfo in ip:
            addr = addrInfo.get('addr')
            if addr is not None:
                addresses.append(addr.split("%")[0])
            if '127.0.0.1' in addresses:
                addresses.remove('127.0.0.1')
    return addresses


def ipv4_networks():
    addr_family = netifaces.AF_INET
    addresses = []

    for inter in netifaces.interfaces():
        ip = netifaces.ifaddresses(inter).get(addr_family)
        if not ip:
            continue
        for addrInfo in ip:
            addr = unicode(addrInfo.get('addr'))
            mask = unicode(addrInfo.get('netmask', '255.255.255.0'))

            try:
                ip_addr = ipaddress.ip_network((addr, mask), strict=False)
            except Exception as exc:
                logger.error("Error parsing ip address {}: {}".format(addr, exc))
                continue

            if addr != '127.0.0.1':
                split = unicode(ip_addr).split('/')
                addresses.append((split[0], split[1]))
    return addresses


ip4Addresses = ip_addresses
get_host_addresses = ip_addresses


def ip_address_private(address):
    if address.find(':') != -1:
        try:
            return ipaddress.IPv6Address(unicode(address)).is_private
        except Exception as exc:
            logger.error("Cannot parse IPv6 address {}: {}"
                         .format(address, exc))
            return False
    try:
        return ipaddress.IPv4Address(unicode(address)).is_private
    except Exception as exc:
        logger.error("Cannot parse IPv4 address {}: {}"
                     .format(address, exc))
        return False


def ip_network_contains(network, mask, address):
    return ipaddress.ip_network((network, mask), strict=False) == \
           ipaddress.ip_network((unicode(address), mask), strict=False)


def get_host_address_from_connection(connect_to=DEFAULT_CONNECT_TO, connect_to_port=DEFAULT_CONNECT_TO_PORT,
                                     use_ipv6=False):
    """Get host address by connecting with given address and checking which one of host addresses was used
    :param str connect_to: address that host should connect to
    :param int connect_to_port: port that host should connect to
    :param bool use_ipv6: *Default: False* should IPv6 be use to connect?
    :return str: host address used to connect
    """
    if use_ipv6:
        addr_family = socket.AF_INET6
    else:
        addr_family = socket.AF_INET
    return [(s.connect((connect_to, connect_to_port)), s.getsockname()[0], s.close())
            for s in [socket.socket(addr_family, socket.SOCK_DGRAM)]][0][1]


def get_external_address(source_port=0):
    """ Method try to get host public address with STUN protocol
    :param int source_port: port that should be used for connection.
    If 0, a free port will be picked by OS.
    :return (str, int, str): tuple with host public address, public port that is
    mapped to local <source_port> and this host nat type
    """
    nat_type, external_ip, external_port = stun.get_ip_info(source_port=source_port)
    logger.debug("NAT {}, external [{}] {}".format(nat_type, external_ip, external_port))
    return external_ip, external_port, nat_type


def get_host_address(seed_addr=None, use_ipv6=False):
    """
    Return this host most useful internet address. Host will try to connect with outer service to determine the address.
    If connection fail, one of the private address will be used - the one with longest common prefix with given address
    or the first one if seed address is None
    :param None|str seed_addr: seed address that may be used to compare addresses
    :param bool use_ipv6: if True then IPv6 address will be determine, otherwise IPv4 address
    :return str: host address that is most probably the useful one
    """
    try:
        ip = get_host_address_from_connection(use_ipv6=use_ipv6)
        if ip is not None:
            return ip

    except Exception as err:
        logger.error("Can't connect to outer service: {}".format(err))

    try:
        ips = ip_addresses(use_ipv6)
        if seed_addr is not None:
            len_pref = [len(os.path.commonprefix([addr, seed_addr])) for addr in ips]
            return ips[len_pref.index(max(len_pref))]
        else:
            if len(ips) < 1:
                raise Exception("Netifaces return empty list of addresses")
            return ips[0]
    except Exception as err:
        logger.error("get_host_address error {}".format(str(err)))
        return socket.gethostbyname(socket.gethostname())
