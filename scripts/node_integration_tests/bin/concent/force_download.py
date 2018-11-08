#!/usr/bin/env python
from scripts.node_integration_tests.playbooks import run, force_download

run.run_playbook(force_download.ForceDownload)  # type: ignore
