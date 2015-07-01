import socket
import os
import logging
import netifaces
import stun

logger = logging.getLogger(__name__)

#Stara metoda, dziala dobrze pod windowsem, ale nie pod linuxem (zwraca glownie 127.0.0.1)
#def ip4_addresses():
#   return [i[4][0] for i in socket.getaddrinfo(socket.gethostname(), 0, socket.AF_INET)]


#######################################################################################
def ipAddresses(useIp6=False):
    if useIp6:
        addrFamily = netifaces.AF_INET6
    else:
        addrFamily = netifaces.AF_INET
    addresses = []
    for inter in netifaces.interfaces():
        ip = netifaces.ifaddresses(inter).get(addrFamily)
        if ip is None:
            continue
        for addrInfo in ip:
            addr = addrInfo.get('addr')
            if addr is not None:
                addresses.append(addr)
        #FIXME Tej instrukcji w ogole nie powinno byc, gdy bedziemy umieli kontynuowac nieprawdilowe lokalne polaczenia
        # Lokalny adres odpowiada, ale nie jest tym poszukiwanym
        if '127.0.0.1' in addresses:
            addresses.remove('127.0.0.1')
    return []

ip4Addresses = ipAddresses
getHostAddresses = ipAddresses


#######################################################################################
DEFAULT_CONNECT_TO = '8.8.8.8'
DEFAULT_CONNECT_TO_PORT = 80

#######################################################################################
def getHostAddressFromConnection(connectTo=DEFAULT_CONNECT_TO, connectToPort=DEFAULT_CONNECT_TO_PORT, useIp6=False):
    if useIp6:
        addrFamily = socket.AF_INET6
    else:
        addrFamily = socket.AF_INET
    return [(s.connect((connectTo, connectToPort)), s.getsockname()[0], s.close()) for s in [socket.socket(addrFamily, socket.SOCK_DGRAM)]][0][1]

#######################################################################################
def getExternalAddress(sourcePort=None):
    if sourcePort:
        natType, externalIp, externalPort = stun.get_ip_info(source_port=sourcePort)
    else:
        natType, externalIp, externalPort = stun.get_ip_info()
    logger.debug("natType {}, externalIp {}, externalPort {}".format(natType, externalIp, externalPort))
    return (externalIp, externalPort)

#######################################################################################
def getHostAddress(seedAddr = None, useIp6=False):
    try:
        ip = getHostAddressFromConnection(useIp6=useIp6)
        print "IP {}".format(ip)
        if ip is not None:
            return ip
    except Exception, err:
        logger.error("Can't connect to outer service: {}".format(err))

    ips = ipAddresses(useIp6)
    try:
        if seedAddr is not None:
            lenPref = [len(os.path.commonprefix([addr, seedAddr])) for addr in ips]
            return ips[lenPref.index(max(lenPref))]
        else:
            return ips[0]
    except Exception, err:
        logger.error("getHostAddress error {}".format(str(err)))
        return socket.gethostbyname(socket.gethostname())
