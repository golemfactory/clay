import logging

import jsonpickle
from peewee import IntegrityError

from golem.model import TaskPreset

logger = logging.getLogger("golem.task")


def save_task_preset(task_name, data):
    try:
        task_def = jsonpickle.loads(data)
        try:
            TaskPreset.create(name=task_name,
                              task_type=task_def.task_type,
                              data=data)
        except IntegrityError:
            is_same_preset = _is_same_task_preset(task_def.task_type, task_name)
            TaskPreset.update(data=data).where(is_same_preset).execute()
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
            remove_preset(task_preset.task_type, task_preset.name)
    return proper_presets


def remove_preset(task_type, name):
    try:
        query = TaskPreset.delete().where(_is_same_task_preset(task_type, name))
        query.execute()
    except Exception:
        logger.exception(("Canont remove task preset {}:{}".format(task_type,
                                                                   name)))


def _is_same_task_preset(task_type, name):
    return (TaskPreset.task_type == task_type) & (TaskPreset.name == name)
