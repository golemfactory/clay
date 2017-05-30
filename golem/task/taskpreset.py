import logging

import jsonpickle
from peewee import IntegrityError

from golem.model import TaskPreset

logger = logging.getLogger("golem.task")


def save_task_preset(preset_name, task_type, data):
    try:
        try:
            TaskPreset.create(name=preset_name,
                              task_type=task_type,
                              data=data)
        except IntegrityError:
            is_same_preset = _is_same_task_preset(task_type,
                                                  preset_name)
            TaskPreset.update(data=data).where(is_same_preset).execute()
    except Exception:
        logger.exception("Cannot save preset")


def get_task_presets(task_type):
    task_presets = TaskPreset.select().where(TaskPreset.task_type == task_type)
    proper_presets = {task_preset.name: task_preset.data
                      for task_preset in task_presets}
    return proper_presets


def delete_task_preset(task_type, name):
    try:
        query = TaskPreset.delete().where(_is_same_task_preset(task_type, name))
        query.execute()
    except Exception:
        logger.exception(("Cannot remove task preset {}:{}".format(task_type,
                                                                   name)))


def _is_same_task_preset(task_type, name):
    return (TaskPreset.task_type == task_type) & (TaskPreset.name == name)
