import os

# pylint: disable=import-error
import params  # This module is generated before this script is run
import golem_remote as golem
from golem_remote.runf_helpers import SubtaskData

# sys.path.append(os.path.join(params.RESOURCES_DIR, "code"))
# sys.path.append(os.path.join(params.WORK_DIR))  # for messages.py

data: SubtaskData = golem.decode_str_to_obj(params.data)


# black magic
import builtins  # pylint: disable=wrong-import-position
golem.open_file.orig_open = open
builtins.open = golem.open_file.open_file(original_dir=data.original_dir)


solution = data.function(*data.args, **data.kwargs)
solution = golem.encode_obj_to_str(solution)

result_path = os.path.join(params.OUTPUT_DIR, f"out.{params.RESULT_EXT}")

with open(result_path, "w") as f:
    f.write(solution)
