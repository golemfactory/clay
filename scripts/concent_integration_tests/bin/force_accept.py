#!/usr/bin/env python
from scripts.concent_integration_tests.playbooks import run, force_accept

run.run_playbook(force_accept.ForceAccept)  # type: ignore
