#!/usr/bin/env python
from scripts.concent_integration_tests.tests.playbooks import regular_run, run


run.run_playbook(regular_run.RegularRun)
