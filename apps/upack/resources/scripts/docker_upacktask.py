from __future__ import print_function

import imp
import os
from shutil import copyfile
from distutils.dir_util import copy_tree
import subprocess
import uuid

import params  # This module is generated before this script is run

def run():
    code_file = os.path.join(params.RESOURCES_DIR, "code", "computing.py")
    computing = imp.load_source("code", code_file)

    src = os.path.join(params.RESOURCES_DIR, "data")
    dst = os.path.join(params.WORK_DIR, "data")
    copy_tree(src, dst)
    computing.run_upack_task(dst)
    copy_tree(dst, params.OUTPUT_DIR)

run()
