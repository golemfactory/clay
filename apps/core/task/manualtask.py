import copy
import logging
import threading
import time
from collections import defaultdict

from golem_messages import message

from apps.core.task.coretask import CoreTask
from apps.core.task.coretaskstate import TaskDefinition
from golem.network.transport.communicator import Communicator
from golem.task.taskbase import AcceptClientVerdict


logger = logging.getLogger(__name__)


class ManualTask(CoreTask):
    def is_provider_chosen_manually(self):
        return True
