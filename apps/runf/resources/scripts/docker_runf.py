import os
import sys

# pylint: disable=import-error
from pathlib import Path

import params  # This module is generated before this script is run

# slightly hackish way to not run a benchmark at all
if hasattr(params, "BENCHMARK") and params.BENCHMARK:
    sys.exit(0)

import golem_remote as golem
from golem_remote import open_file
from golem_remote.runf_helpers import SubtaskData

# raise Exception(list(golem.open_file.list_dir_recursive(Path("/golem/resources"))))

# sys.path.append(os.path.join(params.RESOURCES_DIR, "code"))
# sys.path.append(os.path.join(params.WORK_DIR))  # for messages.py

data: SubtaskData = golem.decode_str_to_obj(params.data)


# black magic
import builtins  # pylint: disable=wrong-import-position
open_file.orig_open = open
builtins.open = open_file.open_file(original_dir=data.params.original_dir)


solution = data.function(*data.args, **data.kwargs)
solution = golem.encode_obj_to_str(solution)

result_path = os.path.join(params.OUTPUT_DIR, f"out.{params.RESULT_EXT}")

with open(result_path, "w") as f:
    f.write(solution)
