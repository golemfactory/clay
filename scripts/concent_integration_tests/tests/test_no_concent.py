#!/usr/bin/env python
from scripts.concent_integration_tests.tests.playbooks import no_concent, run


run.run_playbook(no_concent.NoConcent)  # type: ignore
