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
from golem.task.taskstate import TaskStatus
from golem.model import Performance

logger = logging.getLogger(__name__)

ACCEPTABLE_PERFORMANCE = 500


def run_benchmark_error_performance_0(self, benchmark, task_builder, env_id,
                                      success=None, error=None):
    logger.info('Running benchmark for %s', env_id)

    from golem_messages.datastructures.p2p import Node

    def success_callback(performance: Performance):
        logger.info('%s benchmark finished. performance=%.2f, cpu_usage=%d',
                    env_id, performance.value, performance.cpu_usage)
        performance.upsert()
        if success:
            success(performance.value)

    def error_callback(err: Union[str, Exception]):
        logger.error("Unable to run %s benchmark: %s", env_id, str(err))
        Performance(
            environment_id=env_id,
            value=ACCEPTABLE_PERFORMANCE
        ).upsert()

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
        benchmark=benchmark,
        env_id=env_id
    )
    br.run()


def wait_failure(self, timeout=None):
    return -1


with mock.patch("golem.docker.job.DockerJob.wait",
                wait_failure), mock.patch('golem.task.benchmarkmanager.'
                                          'BenchmarkManager.run_benchmark',
                                          run_benchmark_error_performance_0):
    main()
