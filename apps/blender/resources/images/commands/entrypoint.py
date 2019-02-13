from pathlib import Path

import click

from create_task import create_task as create_task_impl
from get_subtask import get_subtask as get_subtask_impl
from compute import compute as compute_impl
from verify import verify as verify_impl
from benchmark import benchmark as benchmark_impl


WORK_DIR = Path('/work')
RESOURCES_DIR = Path('/resources')
NETWORK_RESOURCES_DIR = Path('/network_resources')
RESULTS_DIR = Path('/results')
NETWORK_RESULTS_DIR = Path('/network_results')
BENCHMARK_DIR = Path('/benchmark')


@click.group()
def main():
    pass


@main.command()
def create_task():
    create_task_impl(
        # WORK_DIR,
        # RESOURCES_DIR,
        # NETWORK_RESOURCES_DIR,
        Path('/tmp/blender_docker/req/work'),
        Path('/tmp/blender_docker/req/resources'),
        Path('/tmp/blender_docker/req/network_resources'),
    )


@main.command()
def get_subtask():
    get_subtask_impl(
        # WORK_DIR,
        # RESOURCES_DIR,
        # NETWORK_RESOURCES_DIR,
        Path('/tmp/blender_docker/req/work'),
        Path('/tmp/blender_docker/req/resources'),
        Path('/tmp/blender_docker/req/network_resources'),
    )


@main.command()
def compute():
    compute_impl(
        # WORK_DIR,
        # NETWORK_RESOURCES_DIR,
        Path('/tmp/blender_docker/prv/work'),
        Path('/tmp/blender_docker/prv/network_resources'),
    )


@main.command()
@click.argument('subtask_id')
def verify(subtask_id: str):
    verify_impl(
        subtask_id,
        # WORK_DIR,
        # RESOURCES_DIR,
        # NETWORK_RESOURCES_DIR,
        # RESULTS_DIR,
        # NETWORK_RESULTS_DIR,
        Path('/tmp/blender_docker/req/work'),
        Path('/tmp/blender_docker/req/resources'),
        Path('/tmp/blender_docker/req/network_resources'),
        Path('/tmp/blender_docker/req/results'),
        Path('/tmp/blender_docker/req/network_results'),
    )


@main.command()
def benchmark():
    benchmark_impl(
        # WORK_DIR,
        # BENCHMARK_DIR,
        Path('/tmp/blender_docker/req/benchmark_work'),
        Path('/tmp/blender_docker/req/benchmark'),
    )


if __name__ == "__main__":
    main()
