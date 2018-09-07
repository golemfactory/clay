import base64
import codecs
import json
import os
from typing import Any, NamedTuple, List, Dict, Callable

import cloudpickle as pickle
# pylint: disable=import-error
import params  # This module is generated before this script is run

# sys.path.append(os.path.join(params.RESOURCES_DIR, "code"))
# sys.path.append(os.path.join(params.WORK_DIR))  # for messages.py


# source: golem_remote/encoding.py
# TODO change that to normal import when golem_remote will be published on pypi
def decode_str_to_obj(s: str):
    result = json.loads(s)
    result = result["r"]
    result = codecs.encode(result, "ascii")
    result = base64.b64decode(result)
    result = pickle.loads(result)
    return result

def encode_obj_to_str(obj: Any):
    result = pickle.dumps(obj)
    result = base64.b64encode(result)
    result = codecs.decode(result, "ascii")
    result = {"r": result}
    result = json.dumps(result)
    return result

# class SubtaskData(NamedTuple):
#     args: List[Any]
#     kwargs: Dict[str, Any]
#     function: Callable[..., Any]


data = decode_str_to_obj(params.data)

solution = data.function(*data.args, **data.kwargs)
# solution = data["function"](*data["args"], **data["kwargs"])
solution = encode_obj_to_str(solution)

# result_path = os.path.join(params.OUTPUT_DIR, f"{params.subtask_id}.{params.RESULT_EXT}")
result_path = os.path.join(params.OUTPUT_DIR, f"out.{params.RESULT_EXT}")

with open(result_path, "w") as f:
    f.write(solution)
