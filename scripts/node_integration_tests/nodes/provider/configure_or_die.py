#!/usr/bin/env python

import logging
from unittest.mock import patch

from twisted.internet.defer import inlineCallbacks

from golemapp import main

from golem.client import Client
from golem.task.taskserver import TaskServer


def on_exception():
    logging.critical("#### Integration test failed ####")


client_change_config_orig = Client.change_config


def client_change_config(self: Client, *args, **kwargs):
    try:
        client_change_config_orig(self, *args, **kwargs)
    except:  # noqa pylint: disable=broad-except
        on_exception()


task_server_change_config_orig = TaskServer.change_config


@inlineCallbacks
def task_server_change_config(self: TaskServer, *args, **kwargs):
    try:
        yield task_server_change_config_orig(self, *args, **kwargs)
    except:  # noqa pylint: disable=broad-except
        on_exception()


with patch("golem.client.Client.change_config",
           client_change_config), \
     patch("golem.task.taskserver.TaskServer.change_config",
           task_server_change_config):
    main()
