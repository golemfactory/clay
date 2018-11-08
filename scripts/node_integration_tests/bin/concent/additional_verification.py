#!/usr/bin/env python
from scripts.node_integration_tests.playbooks import (
    run, additional_verification
)

run.run_playbook(additional_verification.AdditionalVerification)  # type: ignore
