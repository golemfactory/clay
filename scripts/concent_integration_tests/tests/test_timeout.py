#!/usr/bin/env python
from scripts.concent_integration_tests.tests.playbooks import task_timeout, run


run.run_playbook(task_timeout.TaskTimeoutAndRestart)  # type: ignore
