import logging

import jsonpickle
from peewee import IntegrityError

from golem.model import TaskPreset

logger = logging.getLogger("golem.task")


def save_task_preset(data):
    try:
        task_def = jsonpickle.loads(data)
        try:
            TaskPreset.create(name=task_def.task_name,
                              task_type=task_def.task_type,
                              data=data)
        except IntegrityError:
            TaskPreset.update(name=task_def.task_name,
                              task_type=task_def.task_type,
                              data=data)
    except Exception:
        logger.exception("Cannot save preset")


def load_task_preset(data):
    try:
        TaskPreset.get


