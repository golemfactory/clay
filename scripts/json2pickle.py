#!/usr/bin/env python
import jsonpickle
import pickle
import sys

if len(sys.argv) != 3:
    print "Usage: {} <json-file> <pickle-file>".format(sys.argv[0])
    sys.exit(1)

with open(sys.argv[1], 'r') as input_file:
    with open(sys.argv[2], 'w') as output_file:
        obj = jsonpickle.decode(input_file.read())
        pickle.dump(obj, output_file)
