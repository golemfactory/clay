#!/usr/bin/env python
from scripts.node_integration_tests.playbooks import run, task_timeout

run.run_playbook(task_timeout.TaskTimeoutAndRestart)  # type: ignore
