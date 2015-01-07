import socket
import os
import logging

logger = logging.getLogger(__name__)

def ip4_addresses():
    return [i[4][0] for i in socket.getaddrinfo(socket.gethostname(), 0, socket.AF_INET)]

def getHostAddress( seedAddr = None):
    ips = ip4_addresses()
    try:
        if seedAddr is not None:
            lenPref = [ len( os.path.commonprefix( [addr, seedAddr] ) ) for addr in ips ]
            return ips[ lenPref.index( max( lenPref ) ) ]
    except Exception, err:
        logger.error( "getHostAddress error {}".format( str( err ) ) )
        return socket.gethostbyname( socket.gethostname() )
        #for ip in ips:
        #    if ip.startswith('10.30.'):
        #        return ip

        #for ip in ips:
        #    if not ip.startswith("127."):
        #         return ip
        #return ips[0]
    #return socket.gethostbyname( socket.gethostname() )
