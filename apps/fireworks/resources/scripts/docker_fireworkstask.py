from __future__ import print_function

import imp
import os
from fireworks import LaunchPad, FWorker
from fireworks.core.rocket_launcher import launch_rocket

import params  # This module is generated before this script is run

launchpad = LaunchPad.from_dict(params.launchpad)
launch_rocket(launchpad, FWorker())
