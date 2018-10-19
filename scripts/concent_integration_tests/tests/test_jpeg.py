#!/usr/bin/env python
from scripts.concent_integration_tests.tests.playbooks import (
    regular_run_jpeg, run
)


run.run_playbook(regular_run_jpeg.RegularRun)  # type: ignore
