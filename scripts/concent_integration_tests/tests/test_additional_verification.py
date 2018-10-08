#!/usr/bin/env python
from scripts.concent_integration_tests.tests.playbooks import (
    additional_verification, run
)

run.run_playbook(additional_verification.AdditionalVerification)  # type: ignore
