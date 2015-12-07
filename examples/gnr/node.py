"""GNR Compute Node"""

import os
import argparse
import logging.config
from golem.client import create_client
from renderingenvironment import BlenderEnvironment
from twisted.internet import reactor

config_file = os.path.join(os.path.dirname(__file__), "logging.ini")
logging.config.fileConfig(config_file, disable_existing_loggers=False)

client = create_client()
blender_env = BlenderEnvironment()
blender_env.accept_tasks = True
client.environments_manager.add_environment(blender_env)

parser = argparse.ArgumentParser(description='GNR Compute Node')
parser.add_argument('--seed', type=str)
args = parser.parse_args()
if args.seed:
    host, port = args.seed.split(':')
    client.config_desc.seed_host = host
    client.config_desc.seed_port = int(port)
    # FIXME: Client has .cfg.set_seed_host() method but it does not work


client.start_network()

reactor.run()
