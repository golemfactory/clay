import socket

def ip4_addresses():
    return [i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None) if ':' not in i[4][0]]
    

def getHostAddress():
    ips = ip4_addresses()
    for ip in ips:
        if ip.startswith("10."):
            return ip

    return ""