#!/usr/bin/python

import subprocess
import atexit
import signal
import time
import sys

def stop_me(ps):
    print("stop ps")
    ps.terminate()
    print("stopped ps")
    ps.wait()
    print("ps finished")

def handler(signum, frame):
    print("handler: {}, {}".format(signum, frame))
    sys.exit()

args = ['geth', '2>&1', '|', 'tee', 'test.log']

ps = subprocess.Popen(" ".join(args), shell=True, close_fds=True)

atexit.register(lambda: stop_me(ps))

signal.signal(signal.SIGINT, handler)

while True:
    time.sleep(0.1)
