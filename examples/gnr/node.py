"""GNR Compute Node"""

import os
import logging.config
from golem.client import start_client
from renderingenvironment import BlenderEnvironment
from twisted.internet import reactor

config_file = os.path.join(os.path.dirname(__file__), "logging.ini")
logging.config.fileConfig(config_file, disable_existing_loggers=False)

client = start_client()
blender_env = BlenderEnvironment()
blender_env.accept_tasks = True
client.environments_manager.add_environment(blender_env)

reactor.run()
