#!/usr/bin/env python
from scripts.concent_integration_tests.tests.playbooks import force_report, run


run.run_playbook(force_report.ForceReport)  # type: ignore

