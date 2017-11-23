import json


local_settings = json.load(open('/home/buildbot/site_settings.json'))
buildbot_host = local_settings['host']
