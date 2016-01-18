import json
import os
import re
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


def prepare_task_resources(task):
    """Prepare a new task file with paths rewritten to match location of
    of resource file at the target node:
    - main scene file <scene-dir>/<scene>.blend will be copied to
      IMUNES_TEST_DIR/scene-<scene>.blend at the requester node
    - main program file <prog-path>/<program>.py will be copied to
      IMUNES_TEST_DIR/program-<program>.py at the requester node
    - task file <task-path>/<task>.json will be copied to
      IMUNES_TEST_DIR/task.json at the requester node
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
    Determine default seed and requester nodes, based on node names.
    :param str[] node_names: list of node names
    :param dict(str, NodeInfo) node_infos:
    """
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
        himage_cmd += " | tee /log/golem.log"

        cmd = "xterm -geom 150x30 -e himage {} /bin/sh -c \"{}\" &".format(
            name, himage_cmd)
        print "Running '{}' on {}...".format(himage_cmd, name)
        info.pid = subprocess.Popen(cmd, shell=True)
        time.sleep(1)


TASK_ADDED_RE = re.compile(".*Task ([0-9a-f\-]+) added")
RESOURCES_SEND_RE = re.compile(".*Resources for task ([0-9a-f\-]+) sent")
TASK_ACCEPTED_RE = re.compile(".*Task ([0-9a-f\-]+) accepted")
TASK_NOT_ACCEPTED_RE = re.compile(".*Task ([0-9a-f\-]+) not accepted")


class IllegalStateException(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)


def wait_for_task_completion(requester_name, num_tasks=1):
    """
    Watch log file /log/golem.log at the node requester_name for events related
    to task progress.
    :param str requester_name: name of the task requester node
    :param num_tasks: number of tasks to watch
    """
    print "Waiting for tasks to complete..."
    with open("/tmp/imunes/" + requester_name + "/golem.log", 'r') as log_file:
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

    if len(sys.argv) != 3:
        print "Usage: sudo python " + __file__ +\
              " <topology-file>.imn <task-file>.json"
        sys.exit(1)

    topology_file = sys.argv[1]
    task_file = sys.argv[2]

    with open(task_file, 'r') as tf:
        task_json = json.load(tf)

    # Convert paths in the task file to match resource file locations
    # at the requester node
    converted_task_file, files_to_copy = prepare_task_resources(task_json)

    # Start imunes
    names, infos = start_simulation(topology_file)
    requester = set_default_seed_and_requester(names, infos)
    infos[requester].tasks = [converted_task_file]

    # Copy resource files to the requester node
    for src, dst in files_to_copy.iteritems():
        copy_file(requester, src, dst)

    # 3... 2... 1...
    time.sleep(1)
    start_golem(infos)

    # TODO: instead of waiting 60 sec we should monitor the logs to see when
    # the computation ends (or fails)
    wait_for_task_completion(requester)

    time.sleep(10)
    stop_simulation()
