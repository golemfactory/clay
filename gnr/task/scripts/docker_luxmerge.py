import subprocess
import sys

import params # This module is generated before the script is run

LUXMERGER_COMMAND = "luxmerger"
OUTPUT_DIR = "/golem/output"
WORK_DIR = "/golem/work"
RESOURCE_DIR = "/golem/resource"


def format_lux_merger_cmd(output_filename, new_flm):
    cmd = ["{}".format(LUXMERGER_COMMAND),
           "{}".format(output_filename),
           "{}".format(new_flm),
           "-o", "{}".format(output_filename)]
    return cmd


def exec_cmd(cmd):
    pc = subprocess.Popen(cmd)
    return pc.wait()


def run_lux_merger_task(output_filename, new_flm):
    cmd = format_lux_merger_cmd(output_filename, new_flm)
    exit_code = exec_cmd(cmd)
    if exit_code is not 0:
        sys.exit(exit_code)


run_lux_merger_task(params.output_flm, params.new_flm)
