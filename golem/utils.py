import psutil


def find_free_net_port(start_port):
    """Finds first free port on host starting from given one"""
    open_ports = set(c.laddr[1] for c in psutil.net_connections())
    while start_port in open_ports:
        start_port += 1
    return start_port
