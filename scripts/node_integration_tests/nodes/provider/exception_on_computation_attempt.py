#!/usr/bin/env python
"""

Provider node that refuses to compute the task
because of a docker image problem

"""

import logging
import mock
from typing import Union

from golemapp import main

from apps.core.benchmark.benchmarkrunner import BenchmarkRunner
from apps.core.task.coretaskstate import TaskDesc
from golem.envs import BenchmarkResult
from golem.model import Performance
from golem.task.taskstate import TaskStatus

logger = logging.getLogger(__name__)

ACCEPTABLE_PERFORMANCE = 500


def run_benchmark_error_performance_0(self, benchmark, task_builder, env_id,
                                      success=None, error=None):
    logger.info('Running benchmark for %s', env_id)

    from golem_messages.datastructures.p2p import Node

    def success_callback(result: BenchmarkResult):
        logger.info('%s benchmark finished. performance=%.2f, cpu_usage=%d',
                    env_id, result.performance, result.cpu_usage)

        Performance.update_or_create(
            env_id=env_id,
            performance=result.performance,
            cpu_usage=result.cpu_usage
        )

        if success:
            success(result.performance)

    def error_callback(err: Union[str, Exception]):
        logger.error("Unable to run %s benchmark: %s", env_id, str(err))

        Performance.update_or_create(
            env_id=env_id,
            performance=ACCEPTABLE_PERFORMANCE,
            cpu_usage=Performance.DEFAULT_CPU_USAGE
        )

        if isinstance(err, str):
            err = Exception(err)

        success(ACCEPTABLE_PERFORMANCE)

    task_state = TaskDesc()
    task_state.status = TaskStatus.notStarted
    task_state.definition = benchmark.task_definition
    self._validate_task_state(task_state)
    builder = task_builder(Node(node_name=self.node_name),
                           task_state.definition,
                           self.dir_manager)
    task = builder.build()
    task.initialize(builder.dir_manager)

    br = BenchmarkRunner(
        task=task,
        root_path=self.dir_manager.root_path,
        success_callback=success_callback,
        error_callback=error_callback,
        benchmark=benchmark
    )
    br.run()


def wait_failure(self, timeout=None):
    return -1


with mock.patch("golem.docker.job.DockerJob.wait",
                wait_failure), mock.patch('golem.task.benchmarkmanager.'
                                          'BenchmarkManager.run_benchmark',
                                          run_benchmark_error_performance_0):
    main()
