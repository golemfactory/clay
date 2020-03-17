import datetime
import itertools
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import tempfile
import threading
import typing

from ethereum.utils import denoms

from . import tasks

from ..tempdir import fix_osx_tmpdir


fix_osx_tmpdir()


class ConfigurationError(Exception):
    pass


def get_testdir() -> Path:
    env_key = 'GOLEM_INTEGRATION_TEST_DIR'
    datadir = os.environ.get(env_key, None)
    if not datadir:
        datadir = tempfile.mkdtemp(prefix='golem-integration-test-')
        os.environ[env_key] = datadir
    return Path(datadir)


def mkdatadir(role: str) -> str:
    return tempfile.mkdtemp(prefix='golem-{}-'.format(role.lower()))


def yesterday() -> datetime.datetime:
    return datetime.datetime.utcnow() - datetime.timedelta(days=1)


def report_termination(exit_code, node_type) -> None:
    if exit_code:
        print("%s subprocess exited with: %s" % (node_type, exit_code))


def gracefully_shutdown(process: subprocess.Popen, node_type: str) -> None:
    process.terminate()
    try:
        print("Waiting for the %s subprocess to shut-down" % node_type)
        process.communicate(None, 60)
        report_termination(process.returncode, node_type)
    except subprocess.TimeoutExpired:
        print(
            "%s graceful shutdown timed-out, issuing sigkill." % node_type)
        process.kill()

    print("%s shut down correctly." % node_type)


def _params_from_dict(d: typing.Dict[str, typing.Any]) -> typing.List[str]:
    return list(
        itertools.chain.from_iterable(
            [k, str(v)] if v is not None else [k] for k, v in d.items()
        )
    )


def run_golem_node(
        node_type: str,
        args: typing.Dict[str, typing.Any],
        nodes_root: typing.Optional[Path] = None
        ) -> subprocess.Popen:
    node_file = node_type + '.py'
    cwd = Path(__file__).resolve().parent
    node_script = str(cwd / 'nodes' / node_file)
    return subprocess.Popen(
        args=['python', node_script, *_params_from_dict(args)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def get_output_queue(process: subprocess.Popen) -> queue.Queue:
    def output_queue(stream, q):
        for line in iter(stream.readline, b''):
            q.put(line)

    q: queue.Queue = queue.Queue()  # wth mypy?
    qt = threading.Thread(target=output_queue, args=[process.stdout, q])
    qt.daemon = True
    qt.start()
    return q


def print_output(q: queue.Queue, prefix: str) -> None:
    try:
        for line in iter(q.get_nowait, None):
            if line is None:
                break
            sys.stdout.write(prefix + line.decode('utf-8'))
    except queue.Empty:
        pass


def clear_output(q: queue.Queue) -> None:
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


def is_task_api_task(task_dict: dict) -> bool:
    return 'golem' in task_dict and 'app' in task_dict


def construct_test_task(task_package_name: str, task_settings: str) \
        -> typing.Dict[str, typing.Any]:
    task_dict = tasks.get_settings(task_settings)
    cwd = Path(__file__).resolve().parent
    tasks_path = (cwd / 'tasks' / task_package_name).glob('**/*')
    resources = [str(f) for f in tasks_path if f.is_file()]

    if is_task_api_task(task_dict):
        task_dict['golem']['resources'] = resources
        task_dict['app']['resources'] = [str(Path(r).name) for r in resources]
    else:
        task_dict['resources'] = resources

    return task_dict


def scene_file_path(task_package_name: str, file_path: str) -> str:
    cwd = Path(__file__).resolve().parent
    full_path = cwd / 'tasks' / task_package_name / file_path
    if not full_path.is_file():
        raise ConfigurationError(
            f"Could not find {file_path} "
            f"(expanded as {full_path} "
            f"in task {task_package_name}"
        )
    return str(full_path)


def set_task_output_path(task_dict: dict, output_path: str) -> None:
    if is_task_api_task(task_dict):
        task_dict['golem']['output_directory'] = output_path
    else:
        task_dict['options']['output_path'] = output_path


def timeout_to_seconds(timeout_str: str) -> float:
    components = timeout_str.split(':')
    return datetime.timedelta(
        hours=int(components[0]),
        minutes=int(components[1]),
        seconds=int(components[2])
    ).total_seconds()


def to_ether(value) -> float:
    return int(value) / denoms.ether


def from_ether(value) -> int:
    return int(value * denoms.ether)
