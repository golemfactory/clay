#!/usr/bin/env python
import sys
from scripts.concent_integration_tests.tests.playbooks import (
    force_download, run
)


run.run_playbook(force_download.ForceDownload)  # type: ignore
