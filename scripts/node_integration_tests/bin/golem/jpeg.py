#!/usr/bin/env python
from scripts.node_integration_tests.playbooks import run, regular_run_jpeg

run.run_playbook(regular_run_jpeg.RegularRun)  # type: ignore
