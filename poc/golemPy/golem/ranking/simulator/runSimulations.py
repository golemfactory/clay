from networkSimulator import NetworkSimulator, PANetworkSimulator

def main():
    ns = NetworkSimulator()
    pan = PANetworkSimulator()
    for i in range(1, 1000):
        ns.add_node()
        pan.add_node()
        ns.sync_network()
        pan.sync_network()
    print "NS maxD {}, minD {}, avgD {}".format(ns.max_degree(), ns.min_degree(), ns.avg_degree())
    print "PAN maxD {}, minD {}, avgD {}".format(pan.max_degree(), pan.min_degree(), pan.avg_degree())




main()