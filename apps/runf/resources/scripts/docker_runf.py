import os

# pylint: disable=import-error
import params  # This module is generated before this script is run
from golem_remote import decode_str_to_obj, encode_obj_to_str

# sys.path.append(os.path.join(params.RESOURCES_DIR, "code"))
# sys.path.append(os.path.join(params.WORK_DIR))  # for messages.py

data = decode_str_to_obj(params.data)

solution = data.function(*data.args, **data.kwargs)
solution = encode_obj_to_str(solution)

result_path = os.path.join(params.OUTPUT_DIR, f"out.{params.RESULT_EXT}")

with open(result_path, "w") as f:
    f.write(solution)
