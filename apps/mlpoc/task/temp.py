import os
import tempfile

import time

from golem.docker.image import DockerImage
from golem.task.localcomputer import LocalComputer
from golem.task.taskbase import ComputeTaskDef

src = \
"""
import time
import params
import os
time.sleep(5)
with open(os.path.join(params.OUTPUT_DIR, 'out'), 'w') as f:
    f.write('Starting docker')
time.sleep(3)
with open(os.path.join(params.OUTPUT_DIR, 'out'), 'a+') as f:
    f.write('Leaving docker')
"""

def get():
    c = ComputeTaskDef()
    c.src_code = src
    c.docker_images = [DockerImage("golemfactory/base", tag="1.2")]
    return c

tmp = tempfile.mkdtemp()
lc = LocalComputer(None,
                   tmp,
                   lambda *_:print("Success"),
                   lambda *_: print("Fail"),
                   get,
                   use_task_resources=False,
                   additional_resources=None)

lc.run()
time.sleep(2)
while not os.listdir(os.path.join(tmp, "tmp", "output")):
    time.sleep(1)

with open(os.path.join(tmp, "tmp", "output", 'out'), 'r') as f:
    txt = f.read()
    print(txt)
print("Concurrent")
time.sleep(5)
with open(os.path.join(tmp, "tmp", "output", 'out'), 'r') as f:
    txt = f.read()
    print(txt)
lc.tt.join()
