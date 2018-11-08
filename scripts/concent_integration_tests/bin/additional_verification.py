#!/usr/bin/env python
from scripts.concent_integration_tests.playbooks import (
    run, additional_verification
)

run.run_playbook(additional_verification.AdditionalVerification)  # type: ignore
