#!/usr/bin/env python
from scripts.node_integration_tests.playbooks import run, regular_run

run.run_playbook(regular_run.RegularRun)  # type: ignore
