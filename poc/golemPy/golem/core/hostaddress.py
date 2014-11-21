import socket

def ip4_addresses():
    return [i[4][0] for i in socket.getaddrinfo(socket.gethostname(), 0, socket.AF_INET)]

def getHostAddress():
    # ips = ip4_addresses()
    # for ip in ips:
    #     if not ip.startswith("127."):
    #         return ip
    # return ips[0]
    return socket.gethostbyname( socket.gethostname() )
