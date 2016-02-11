import json
import jsonpickle
import pickle
import sys

if len(sys.argv) != 3:
    print "Usage: {} <pickle-file> <json-file>".format(sys.argv[0])
    sys.exit(1)

with open(sys.argv[1], 'r') as input_file:
    with open(sys.argv[2], 'w') as output_file:
        unpickled = pickle.load(input_file)
        json_str = jsonpickle.encode(unpickled)
        # For pretty printing we need to read the json back :(
        json_dict = json.loads(json_str)
        json.dump(json_dict, output_file, indent=2, separators=(',', ':'))

