#!/usr/bin/env python
from scripts.node_integration_tests.playbooks import run, no_concent

run.run_playbook(no_concent.NoConcent)  # type: ignore
