import socket
import os
import logging
import netifaces

logger = logging.getLogger(__name__)

#def ip4_addresses():
#   return [i[4][0] for i in socket.getaddrinfo(socket.gethostname(), 0, socket.AF_INET)]


def ip4_addresses():
    addresses = []
    for inter in netifaces.interfaces():
        ipv4 = netifaces.ifaddresses(inter).get(netifaces.AF_INET)
        if ipv4 is None:
            continue
        for addrInfo in ipv4:
            addr = addrInfo.get('addr')
            if addr is not None:
                addresses.append(addr)
    return addresses

def getHostAddressFromConnection():
    return [(s.connect(('8.8.8.8', 80)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]


def getHostAddress(seedAddr = None):
    try:
        ips = getHostAddressFromConnection()
        if ips is not None:
            return ips
    except Exception, err:
        logger.error("Can't connect to outer service: {}".format(err))

    ips = ip4_addresses()
    try:
        if seedAddr is not None:
            lenPref = [len(os.path.commonprefix([addr, seedAddr])) for addr in ips]
            return ips[lenPref.index(max(lenPref))]
        else:
            return ips[0]
    except Exception, err:
        logger.error("getHostAddress error {}".format(str(err)))
        return socket.gethostbyname(socket.gethostname())
