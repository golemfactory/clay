import json
import os
import subprocess
from distutils.dir_util import copy_tree


WASI_SANDBOX_EXECUTABLE_NAME = '/wasmtime'


def run_job():
    with open('params.json', 'r') as params_file:
        params = json.load(params_file)

    input_dir = os.path.join(
        os.environ['RESOURCES_DIR'], params['workdir'])
    # output_dir = os.path.join(
    #     os.environ['OUTPUT_DIR'], params['workdir'], params['name'])
    output_dir = os.environ['OUTPUT_DIR']

    copy_tree(os.path.join(
        input_dir, params['name']), output_dir)

    subprocess.call(
        [
            WASI_SANDBOX_EXECUTABLE_NAME,
            '--mapdir=.:' + output_dir,
            os.path.join(input_dir,
                         os.path.basename(params['bin'])),
        ] + [
            '--',
        ] + params['exec_args'],
        cwd=os.environ['RESOURCES_DIR']
    )


if __name__ == '__main__':
    run_job()
