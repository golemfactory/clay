import argparse
import jsonpickle as json
import os
import re
import subprocess
import sys
import time


EXPERIMENT_NAME = "GOLEM"
DEFAULT_PORT = 40102

# These paths has to end with "/":
IMUNES_GOLEM_DIR = "/opt/golem/"
IMUNES_TEST_DIR = IMUNES_GOLEM_DIR + "test-task/"
assert IMUNES_GOLEM_DIR.endswith("/")
assert IMUNES_TEST_DIR.endswith("/")


class NodeInfo(object):

    def __init__(self, address, is_supernode=False, disable_blender=False):
        self.address = address
        self.peers = []
        self.tasks = []
        self.pid = None
        self.disable_blender = disable_blender
        self.is_supernode = is_supernode


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


def prepare_task_resources(task):
    """Prepare a new task file with paths rewritten to match location of
    of resource file at the target node:
    - main scene file <scene-dir>/<scene>.blend will be copied to
      IMUNES_TEST_DIR/scene-<scene>.blend at the requestor node
    - main program file <prog-path>/<program>.py will be copied to
      IMUNES_TEST_DIR/program-<program>.py at the requestor node
    - task file <task-path>/<task>.json will be copied to
      IMUNES_TEST_DIR/task.json at the requestor node
    - modified task file <task-dir>/<task>.json is stored locally as
      imunes-<task>.json in the current working dir
    For now we assume there are no resource files other than program
    and scene file.
    TODO: handle other resource files.

    :param dict task: original task file, as a dict read from JSON file
    """

    orig_program_file = task["main_program_file"]
    dest_program_file = IMUNES_TEST_DIR + "program-" + \
        os.path.basename(orig_program_file)

    orig_scene_file = task["main_scene_file"]
    dest_scene_file = IMUNES_TEST_DIR + "scene-" + \
        os.path.basename(orig_scene_file)

    task["main_program_file"] = dest_program_file
    task["main_scene_file"] = dest_scene_file
    task["resources"]["py/set"] = [dest_program_file, dest_scene_file]

    modified_task_file = os.path.join(os.getcwd(),
                                      "imunes-" + os.path.basename(task_file))
    with open(modified_task_file, 'w') as f:
        json.dump(task, f, indent=2, separators=(',', ':'))

    dest_task_file = IMUNES_TEST_DIR + "task.json"

    file_mapping = {
        modified_task_file: dest_task_file,
        orig_program_file: dest_program_file,
        orig_scene_file: dest_scene_file
    }
    return dest_task_file, file_mapping


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

    # Give IMUNES some time to set up the network
    time.sleep(2.0)

    print "Imunes experiment '{}' started".format(EXPERIMENT_NAME)
    return node_names


def create_node_infos(node_names, args):
    # Get eth0 network address for each node
    node_infos = {}
    peer_addrs = []
    print "Golem nodes:"
    for node in node_names:
        if not (node.startswith('pc') or node.startswith('host')):
            continue
        address = get_node_address(node)
        is_supernode = node in args.supernode
        disable_blender = node in args.disable_blender
        node_infos[node] = NodeInfo(address, is_supernode, disable_blender)
        print "\t{}: {}{}{}{}{}".format(
                node, address,
                ", super node" if is_supernode else "",
                ", seed node" if node in args.seed else "",
                ", requestor" if node is args.requestor else "",
                ", blender disabled" if disable_blender else "")
        if node in args.seed:
            peer_addrs.append(address)

    for info in node_infos.values():
        for addr in peer_addrs:
            if addr != info.address:
                info.peers.append("{}:{}".format(addr, DEFAULT_PORT))

    return node_infos


def stop_simulation():
    print "Terminating simulation..."
    subprocess.check_call(["imunes", "-b", "-e", EXPERIMENT_NAME])


def setup_nat(node_names):
    """Set up NAT rules at every nodes whose name matches 'nat*'.
    Any such node is assumed to have interfaces 'eth0' (LAN) and 'eth1' (WAN).
    :param list(str) node_names: list of all node names
    """
    config = ["iptables --policy FORWARD DROP",
              "iptables -t nat -A POSTROUTING -o eth1 -j MASQUERADE",
              "iptables -A FORWARD -i eth1 -o eth0 -m state"
              " --state RELATED,ESTABLISHED -j ACCEPT",
              "iptables -A FORWARD -i eth0 -o eth1 -j ACCEPT"]

    for name in node_names:
        if name.startswith('nat'):
            for line in config:
                subprocess.check_call(["himage", name] + line.split())


def copy_file(node_name, src_file, target_file):
    """
    :param str node_name: name of the target node
    :param str src_file: absolute path of the source file
    :param str target_file: absolute path of the target file
    :return:
    """
    print "Copying file {} to {}:{}".format(src_file, node_name, target_file)

    # Make sure that the target dir exists
    if target_file.find("/") != -1:
        target_dir = target_file.rsplit("/", 1)[0]
        if target_dir:
            subprocess.check_call(["himage", node_name,
                                   "mkdir", "-p", target_dir])

    subprocess.check_call(["hcp", src_file, node_name + ":" + target_file])


def start_golem(node_infos, seed_names):
    print "Starting golem instances..."

    def start_node(name, info):
        himage_cmd = "python {}/tests/imunes/node.py".format(IMUNES_GOLEM_DIR)
        if info.address:
            if info.is_supernode:
                himage_cmd += " --public-address " + info.address
            else:
                himage_cmd += " --node-address " + info.address
        for addr in info.peers:
            himage_cmd += " --peer " + addr
        for task in info.tasks:
            himage_cmd += " --task " + task
        if info.disable_blender:
            himage_cmd += " --no-blender"

        cmd = "xterm -title '{} ({})' -geom 150x30 -e " \
              "himage {} /bin/sh -c '{} 2>&1 | tee /log/golem.log' &".format(
                  name, himage_cmd, name, himage_cmd)
        print "Running '{}' on {}...".format(himage_cmd, name)
        info.pid = subprocess.Popen(cmd, shell=True)
        time.sleep(1)

    # First start golem on seed nodes, then on the rest
    [start_node(n, i) for n, i in node_infos.iteritems() if n in seed_names]
    time.sleep(2)
    [start_node(n, i) for n, i in node_infos.iteritems() if n not in seed_names]


TASK_ADDED_RE = re.compile(".*Task ([0-9a-f\-]+) added")
RESOURCES_SEND_RE = re.compile(".*Resources for task ([0-9a-f\-]+) sent")
TASK_ACCEPTED_RE = re.compile(".*Task ([0-9a-f\-]+) accepted")
TASK_NOT_ACCEPTED_RE = re.compile(".*Task ([0-9a-f\-]+) not accepted")


class IllegalStateException(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)


def wait_for_task_completion(requestor_name, num_tasks=1):
    """
    Watch log file /log/golem.log at the node requestor_name for events related
    to task progress.
    :param str requestor_name: name of the task requestor node
    :param num_tasks: number of tasks to watch
    """
    print "Waiting for tasks to complete..."
    with open("/tmp/imunes/" + requestor_name + "/golem.log", 'r') as log_file:
        done = False
        started_tasks = []
        finished_tasks = []
        while not done:
            line = log_file.readline()
            if not line:
                time.sleep(0.2)
                continue
            m = TASK_ADDED_RE.match(line)
            if m:
                task_id = m.group(1)
                print "Task {} added".format(task_id)
                if task_id in started_tasks:
                    raise IllegalStateException(
                        "Task {} already started".format(task_id))
                started_tasks.append(task_id)
                continue
            m = RESOURCES_SEND_RE.match(line)
            if m:
                task_id = m.group(1)
                print "Resources for task {} sent".format(task_id)
                if task_id not in started_tasks:
                    raise IllegalStateException(
                        "Task {} not started yet".format(task_id))
                continue
            m = TASK_ACCEPTED_RE.match(line)
            if m:
                task_id = m.group(1)
                print "Task {} accepted".format(task_id)
                if task_id not in started_tasks:
                    raise IllegalStateException(
                        "Task {} not started yet".format(task_id))
                started_tasks.remove(task_id)
                finished_tasks.append(task_id)
            m = TASK_NOT_ACCEPTED_RE.match(line)
            if m:
                task_id = m.group(1)
                print "Task {} not accepted".format(task_id)
                if task_id not in started_tasks:
                    raise IllegalStateException(
                        "Task {} not started yet".format(task_id))
                started_tasks.remove(task_id)
                finished_tasks.append(task_id)

            if len(finished_tasks) == num_tasks:
                print "All tasks completed"
                return


if __name__ == "__main__":

    if os.geteuid() != 0:
        print "Imunes must be started as root. Sorry..."
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Run network test with specified IMUNES topology file")
    parser.add_argument("topology_file", metavar="<topology-file>.imn",
                        help="IMUNES topology file")
    parser.add_argument("task_file", nargs="?", metavar="<task-file>.json",
                        help="Test task file")
    parser.add_argument("--supernode", action="append", metavar="<node-name>",
                        default=[], help="Name of a super node")
    parser.add_argument("--seed", action="append", metavar="<node-name>",
                        default=[], help="Name of a seed node")
    parser.add_argument("--requestor", metavar="<node-name>",
                        help="Name of the requestor node")
    parser.add_argument("--disable-blender", action="append",
                        default=[], metavar="<node-name>",
                        help="Name of a node with Blender not available")
    parser.add_argument("--dont-terminate", action="store_true",
                        help="Leave the simulation running on exit")
    args = parser.parse_args()

    topology_file = args.topology_file
    task_file = getattr(args, "task_file", None)

    if task_file and not args.requestor:
        print "Task file specified but no requestor node (use --requestor)"
        sys.exit(1)
    if args.requestor and not task_file:
        print "Requestor node specified but no task file"
        sys.exit(1)

    # clean up whatever remained from previous experiments
    subprocess.call(["cleanupAll"])

    if task_file:
        with open(task_file, 'r') as tf:
            task_json = json.load(tf)

        # Convert paths in the task file to match resource file locations
        # at the requestor node
        converted_task_file, files_to_copy = prepare_task_resources(task_json)

    # Start imunes
    names = start_simulation(args.topology_file)

    # Setup NAT on nodes matching 'nat*'
    setup_nat(names)

    infos = create_node_infos(names, args)

    if args.requestor and args.requestor not in infos:
        print "Invalid requestor node specified"
        sys.exit(1)

    if task_file:
        infos[args.requestor].tasks = [converted_task_file]

        # Copy resource files to the requestor node
        for src, dst in files_to_copy.iteritems():
            copy_file(args.requestor, src, dst)

    # 3... 2... 1...
    time.sleep(1)
    start_golem(infos, args.seed)

    # TODO: instead of waiting 60 sec we should monitor the logs to see when
    # the computation ends (or fails)
    if task_file:
        wait_for_task_completion(args.requestor)

    time.sleep(10)
    if not args.dont_terminate:
        stop_simulation()
