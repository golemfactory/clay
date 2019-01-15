import datetime
import os
import pathlib
import queue
import re
import subprocess
import sys
import threading
import tempfile
import typing

from . import tasks


def get_testdir():
    env_key = 'GOLEM_INTEGRATION_TEST_DIR'
    datadir = os.environ.get(env_key, None)
    if not datadir:
        datadir = tempfile.mkdtemp(prefix='golem-integration-test-')
        os.environ[env_key] = datadir
    return datadir


def mkdatadir(role: str):
    return tempfile.mkdtemp(prefix='golem-{}-'.format(role.lower()))


def yesterday():
    return datetime.datetime.utcnow() - datetime.timedelta(days=1)


def report_termination(exit_code, node_type):
    if exit_code:
        print("%s subprocess exited with: %s" % (node_type, exit_code))


def gracefully_shutdown(process: subprocess.Popen, node_type: str):
    process.terminate()
    try:
        print("Waiting for the %s subprocess to shut-down" % node_type)
        process.communicate(None, 60)
        report_termination(process.returncode, node_type)
    except subprocess.TimeoutExpired:
        print(
            "%s graceful shutdown timed-out, issuing sigkill." % node_type)
        process.kill()


def run_golem_node(node_type: str, *args):
    node_file = node_type + '.py'
    cwd = pathlib.Path(os.path.realpath(__file__)).parent
    node_process = subprocess.Popen(
        args=['python', str(cwd / 'nodes' / node_file), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return node_process


def get_output_queue(process: subprocess.Popen) -> queue.Queue:
    def output_queue(stream, q):
        for line in iter(stream.readline, b''):
            q.put(line)

    q: queue.Queue = queue.Queue()  # wth mypy?
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


def clear_output(q: queue.Queue):
    try:
        while True:
            q.get_nowait()
    except queue.Empty:
        pass


def search_output(q: queue.Queue, pattern) -> typing.Optional[typing.Match]:
    try:
        for line in iter(q.get_nowait, None):
            if line:
                line = line.decode('utf-8')
                m = re.match(pattern, line)
                if m:
                    return m
    except queue.Empty:
        pass
    return None


def construct_test_task(task_package_name, output_path, task_settings):
    settings = tasks.get_settings(task_settings)
    cwd = pathlib.Path(os.path.realpath(__file__)).parent
    tasks_path = (cwd / 'tasks' / task_package_name).glob('*')
    settings['resources'] = [str(f) for f in tasks_path]
    settings['options']['output_path'] = output_path
    return settings


def timeout_to_seconds(timeout_str: str):
    components = timeout_str.split(':')
    return datetime.timedelta(
        hours=int(components[0]),
        minutes=int(components[1]),
        seconds=int(components[2])
    ).total_seconds()
