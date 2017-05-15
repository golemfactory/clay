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


def load_task_presets(task_type):
    task_presets = TaskPreset.select().where(TaskPreset.task_type == task_type)
    proper_presets = dict()
    for task_preset in task_presets:
        try:
            jsonpickle.loads(task_preset.data)
            proper_presets[task_preset.name] = task_preset.data
        except Exception:
            logger.exception("Cannot load task from task_def (removing broken"
                             "preset)")
            TaskPreset.delete().where(_identify_task_preset(task_preset))

    return proper_presets


def _identify_task_preset(task_def):
    return (TaskPreset.task_type == task_def.task_type) & \
           (TaskPreset.name == task_def.name)
