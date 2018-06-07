import os
import pathlib
import queue
import subprocess
import sys
import threading
import uuid

def report_termination(exit_code, node_type):
    if exit_code:
        print("%s subprocess exited with: %s" % (node_type, exit_code))


def gracefully_shutdown(process: subprocess.Popen, node_type: str):
    process.terminate()
    try:
        print("Waiting for the %s subprocess to shut-down" % node_type)
        exit_code = process.wait(60)
        report_termination(exit_code, node_type)
    except subprocess.TimeoutExpired:
        print(
            "%s graceful shutdown timed-out, issuing sigkill." % node_type)
        process.kill()


def run_golem_node(node_type: str):
    node_file = node_type + '.py'
    cwd = pathlib.Path(os.path.realpath(__file__)).parent
    node_process = subprocess.Popen(
        args=['python', str(cwd / 'nodes' / node_file)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return node_process


def get_output_queue(process: subprocess.Popen):
    def output_queue(stream, q):
        for line in iter(stream.readline, b''):
            q.put(line)

    q = queue.Queue()
    qt = threading.Thread(target=output_queue, args=[process.stdout, q])
    qt.daemon = True
    qt.start()
    return q


def print_output(q: queue.Queue, prefix):
    try:
        for line in iter(q.get_nowait, None):
            if line is None:
                break
            sys.stdout.write(prefix + line.decode('utf-8'))
    except queue.Empty:
        pass


def construct_test_task(task_package_name, output_path):
    cwd = pathlib.Path(os.path.realpath(__file__)).parent
    tasks_path = (cwd / 'tasks' / task_package_name).glob('*')
    return {
        'id': str(uuid.uuid4()),
        'type': "Blender",
        'name': 'test task',
        'timeout': "0:10:00",
        "subtask_timeout": "0:09:50",
        "subtasks": 1,
        "bid": 1.0,
        "resources": [str(f) for f in tasks_path],
        "options": {
            "output_path": output_path,
            "format": "PNG",
            "resolution": [
                320,
                240
            ]
        }
    }
