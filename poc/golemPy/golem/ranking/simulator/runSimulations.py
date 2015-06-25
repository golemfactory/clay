from networkSimulator import NetworkSimulator, PANetworkSimulator

def main():
    ns = NetworkSimulator()
    pan = PANetworkSimulator()
    for i in range(1, 1000):
        ns.addNode()
        pan.addNode()
        ns.syncNetwork()
        pan.syncNetwork()
    print "NS maxD {}, minD {}, avgD {}".format(ns.maxDegree(), ns.minDegree(), ns.avgDegree())
    print "PAN maxD {}, minD {}, avgD {}".format(pan.maxDegree(), pan.minDegree(), pan.avgDegree())




main()