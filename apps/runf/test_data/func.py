import json

from .deps.dep1 import mul
from .deps.dep2 import add


def run(a, b, c=0):

    with open("in.json", "r") as f:
        params = json.load(f)

    x = mul(add(a, b), c)
    y = params["param1"] + params["param2"]
    return x * y
