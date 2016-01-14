import os
import subprocess
import sys
import time


EXPERIMENT_NAME = "golem"


class NodeInfo(object):

    def __init__(self, address=None, peers=[], tasks=[]):
        self.address = address
        self.peers = peers
        self.tasks = tasks
        self.pid = None


def get_node_address(node_name):
    output = subprocess.check_output(["himage", node_name, "ifconfig"])
    addr_line_found = False
    for line in output.split("\n"):
        if addr_line_found:
            prefix = "inet addr:"
            i = line.index(prefix)
            j = i + len(prefix)
            k = line.index(" ", j)
            return line[j:k]
        # skip to the first interface other than 'lo' or 'ext0'
        if line == "" or line.startswith(" "):
            continue
        intf_name = line.split(" ", 1)[0]
        if intf_name != "lo" and intf_name != "ext0":
            addr_line_found = True


def start_simulation(network_file):
    print "Starting simulation, using network topology from {}...".format(
        network_file)

    # Run imunes in the background
    subprocess.check_call(["imunes", "-e", EXPERIMENT_NAME, "-b", network_file])

    # Parse the experiment name and the node names
    output = subprocess.check_output(["himage", "-l"])
    output = output.strip("\n )")
    experiment_name, rest = output.split(" (", 1)
    node_names = rest.split()

    print "Imunes experiment '{}' started, node names and addresses:"

    # Get eth0 network address for each node
    nodes = {}
    for node in node_names:
        if node.startswith('switch'):
            continue
        address = get_node_address(node)
        nodes[node] = NodeInfo(address)
        print "\t{}: {}".format(node, address)

    return nodes


def stop_simulation():
    print "Terminating simulation..."
    subprocess.check_call(["imunes", "-b", "-e", EXPERIMENT_NAME])


def start_golem(nodes):
    print "Starting golem instances..."
    for name, info in nodes.iteritems():
        himage_cmd = "python /opt/golem/gnr/node.py"
        if info.address:
            himage_cmd += " --node-address " + info.address
        for addr in info.peers:
            himage_cmd += " --peer " + addr
        cmd = "xterm -geom 150x30 -e himage {} {} &".format(
            name, himage_cmd)
        print "Running '{}' on {}...".format(himage_cmd, name)
        info.pid = subprocess.Popen(cmd, shell=True)
        time.sleep(1)


def copy_file(node, src_file, target_file):
    """
    :param str node:     name of the target node
    :param str src_file: absolute path of the source file
    :param target_file:  absolute path of the target file
    :return:
    """
    print "Copying file {} to {}:{}".format(src_file, node, target_file)
    cmd = "hcp {} {}:{}".format(src_file, node, target_file)
    print cmd
    subprocess.check_call(["hcp", src_file, node + ":" + target_file])


if __name__ == "__main__":
    if os.geteuid() != 0:
        print "Imunes must be started as root. Sorry..."
        sys.exit(1)

    # if len(sys.argv) != 3:
    #    print "Usage: sudo python {} <topology-file>.imn" \
    #          "<task-file>.json".format(__file__)
    #    sys.exit(1)

    topology_file = sys.argv[1]
    # task_file = sys.argv[2]
    nodes_info = start_simulation(topology_file)

    # Make the first node a seed
    seed_addr = None
    for name, info in nodes_info.iteritems():
        if not seed_addr:
            seed_addr = info.address
        else:
            info.peers = [seed_addr]

    # Make the first 'pc*' node the task requester
    requester = None
    for name in nodes_info:
        if name.startswith('pc'):
            requester = name

    nodes_info[requester].tasks = ["/opt/golem/task.json"]

    # Copy task file
    copy_file(requester, "../../save/testtask-imunes.json", "/opt/golem/task.json")
    # Copy resources
    copy_file(requester, "../../testtasks/blender/blender_task/scene-Helicopter-27.blend",
              "/opt/golem/testtasks/blender/blender_task/")
    copy_file(requester, "../../examples/tasks/blendertask.py",
              "/opt/golem/examples/tasks/")

    time.sleep(1)
    start_golem(nodes_info)
    time.sleep(10)

    stop_simulation()