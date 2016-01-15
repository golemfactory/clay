import json
import os
import subprocess
import sys
import time


EXPERIMENT_NAME = "golem"
DEFAULT_PORT = 40102

# These paths has to end with "/":
IMUNES_GOLEM_DIR = "/opt/golem/"
IMUNES_TEST_DIR = IMUNES_GOLEM_DIR + "test-task/"
assert IMUNES_GOLEM_DIR.endswith("/")
assert IMUNES_TEST_DIR.endswith("/")


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
    node_infos = {}
    for node in node_names:
        if node.startswith('switch'):
            continue
        address = get_node_address(node)
        node_infos[node] = NodeInfo(address)
        print "\t{}: {}".format(node, address)

    return node_names, node_infos


def stop_simulation():
    print "Terminating simulation..."
    subprocess.check_call(["imunes", "-b", "-e", EXPERIMENT_NAME])


def set_default_seed_and_requester(node_names, node_infos):
    """
    Determine default seed and requester nodes, based on node names
    """
    seed_name = None
    seed_address = None

    # Make the first 'host*' node a seed
    host_names = [name for name in node_names if name.startswith('host')]
    if host_names:
        seed_name = host_names[0]
        seed_address = node_infos[seed_name].address
        for name, info in node_infos.iteritems():
            if name != seed_name:
                info.peers = ["{}:{}".format(seed_address, DEFAULT_PORT)]
    else:
        print "No host* nodes, cannot set default seed name"

    # Make the first 'pc*' node the task requester
    requester_name = None
    pc_names = [name for name in node_names if name.startswith('pc')]
    if pc_names:
        requester_name = pc_names[0]
    else:
        print "No pc* nodes, cannot set default requester name"

    return requester_name


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


def start_golem(node_infos):
    print "Starting golem instances..."
    for name, info in node_infos.iteritems():
        himage_cmd = "python {}/gnr/node.py".format(IMUNES_GOLEM_DIR)
        if info.address:
            himage_cmd += " --node-address " + info.address
        for addr in info.peers:
            himage_cmd += " --peer " + addr
        for task in info.tasks:
            himage_cmd += " --task " + task

        cmd = "xterm -geom 150x30 -e himage {} {} &".format(
            name, himage_cmd)
        print "Running '{}' on {}...".format(himage_cmd, name)
        info.pid = subprocess.Popen(cmd, shell=True)
        time.sleep(1)


if __name__ == "__main__":
    if os.geteuid() != 0:
        print "Imunes must be started as root. Sorry..."
        sys.exit(1)

    if len(sys.argv) != 3:
        print "Usage: sudo python " + __file__ +\
              " <topology-file>.imn <task-file>.json"
        sys.exit(1)

    topology_file = sys.argv[1]
    task_file = sys.argv[2]

    # "Rebase" the test task:
    # - main scene file <scene-dir>/<scene>.blend will be copied to
    #   IMUNES_TEST_DIR/scene-<scene>.blend at the requester node
    # - main program file <prog-path>/<program>.py will be copied to
    #   IMUNES_TEST_DIR/program-<program>.py at the requester node
    # - task file <task-path>/<task>.json will be copied to
    #   IMUNES_TEST_DIR/task.json at the requester node
    # - modified task file <task-dir>/<task>.json is stored locally as
    #   imunes-<task>.json in the current working dir
    # For now we assume there are no resource files other than program
    # and scene file.
    # TODO: handle other resource files.
    with open(task_file, 'r') as f:
        task = json.load(f)

    orig_program_file = task["main_program_file"]
    dest_program_file = IMUNES_TEST_DIR + "program-" + \
                        os.path.basename(orig_program_file)

    orig_scene_file = task["main_scene_file"]
    dest_scene_file = IMUNES_TEST_DIR + "scene-" + \
                      os.path.basename(orig_scene_file)

    dest_task_file = IMUNES_TEST_DIR + "task.json"

    task["main_program_file"] = dest_program_file
    task["main_scene_file"] = dest_scene_file
    task["resources"]["py/set"] = [dest_program_file, dest_scene_file]

    modified_task_file = os.path.join(os.getcwd(),
                                      "imunes-" + os.path.basename(task_file))
    with open(modified_task_file, 'w') as f:
        json.dump(task, f, indent=2, separators=(',',':'))

    # Start imunes
    names, infos = start_simulation(topology_file)
    requester = set_default_seed_and_requester(names, infos)

    # Copy resource files to the requester node
    infos[requester].tasks = [dest_task_file]
    copy_file(requester, modified_task_file, dest_task_file)
    copy_file(requester, orig_program_file, dest_program_file)
    copy_file(requester, orig_scene_file, dest_scene_file)

    # 3... 2... 1...
    time.sleep(1)
    start_golem(infos)

    time.sleep(60)
    # stop_simulation()