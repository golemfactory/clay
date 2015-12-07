"""GNR Compute Node"""

import os
import argparse
import logging.config
from golem.client import create_client
from golem.network.transport.tcpnetwork import TCPAddress
from renderingenvironment import BlenderEnvironment
from twisted.internet import reactor

config_file = os.path.join(os.path.dirname(__file__), "logging.ini")
logging.config.fileConfig(config_file, disable_existing_loggers=False)

logger = logging.getLogger(__name__)


def parse_connect(arg_connect):
    """ Parse connect arguments
    :param arg_connect: string with addresses formed as addr_1:port1,addr_2:port2,[ipv6_addr_3]:port3
    :return list:  list of tcp_address that may be used to call client.connect.
    """
    addresses = []
    arg_addresses = arg_connect.split(",")
    print arg_addresses
    for arg in arg_addresses:
        try:
            if arg.startswith("["):
                addr = __parse_ipv6(arg)
            else:
                addr = __parse_ipv4(arg)
            addresses.append(addr)
        except ValueError:
            logger.warning("Wrong value format {}. Skipping address.".format(arg))
    return addresses


def __parse_ipv6(addr_arg):
    print addr_arg
    host, port = addr_arg.split("]")
    host = host[1:]
    port = int(port[1:])
    return TCPAddress(host, port)


def __parse_ipv4(addr_arg):
    host, port = addr_arg.split(":")
    port = int(port)
    return TCPAddress(host, port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='GNR Compute Node')
    parser.add_argument('--connect', type=str)
    args = parser.parse_args()

    client = create_client()
    blender_env = BlenderEnvironment()
    blender_env.accept_tasks = True
    client.environments_manager.add_environment(blender_env)
    client.start_network()

    if args.connect:
        addresses = parse_connect(args.connect)
        for addr in addresses:
            client.connect(addr)

    reactor.run()


