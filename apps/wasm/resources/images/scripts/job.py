import json
import os
import subprocess


WASM_SANDBOX_EXECUTABLE_NAME = '/wasm-sandbox'


def run_job():
    with open('params.json', 'r') as params_file:
        params = json.load(params_file)

    input_dir = os.path.join(
        os.environ['RESOURCES_DIR'], params['input_dir_name']
    )

    return subprocess.call(
        [
            WASM_SANDBOX_EXECUTABLE_NAME,
            '-O',
            os.environ['OUTPUT_DIR'],
            '-I',
            os.path.join(input_dir, params['name']),
            '-j',
            os.path.join(input_dir, os.path.basename(params['js_name'])),
            '-w',
            os.path.join(input_dir, os.path.basename(params['wasm_name'])),
        ] + [
            el for path in params['output_file_paths'] for el in ('-o', path)
        ] + [
            '--',
        ] + params['exec_args'],
        cwd=os.environ['RESOURCES_DIR']
    )


if __name__ == '__main__':
    exit(run_job())
