#!/usr/bin/env python
from scripts.concent_integration_tests.playbooks import run, force_report

run.run_playbook(force_report.ForceReport)  # type: ignore

