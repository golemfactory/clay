#!/usr/bin/env python
from scripts.concent_integration_tests.tests.playbooks import force_accept, run


run.run_playbook(force_accept.ForceAccept)  # type: ignore
