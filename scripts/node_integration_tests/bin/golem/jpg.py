#!/usr/bin/env python
from scripts.node_integration_tests.playbooks import run, regular_run_jpg

run.run_playbook(regular_run_jpg.RegularRun)  # type: ignore
