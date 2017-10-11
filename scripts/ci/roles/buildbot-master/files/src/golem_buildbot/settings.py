import os
import json


local_settings = json.load(open(os.environ['BUILDBOT_SETTINGS']))
buildbot_host = local_settings['host']
