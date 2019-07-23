import copy
import typing


_TASK_SETTINGS = {
    'default': {
        'type': "Blender",
        'name': 'test task',
        'timeout': "0:10:00",
        "subtask_timeout": "0:09:50",
        "subtasks_count": 1,
        "bid": 1.0,
        "resources": [],
        "options": {
            "output_path": '',
            "format": "PNG",
            "resolution": [
                320,
                240
            ]
        }
    },
    '4-by-3': {
        'type': "Blender",
        'name': 'test task',
        'timeout': "0:15:00",
        "subtask_timeout": "0:09:50",
        "subtasks_count": 6,
        "bid": 1.0,
        "resources": [],
        "options": {
            "output_path": '',
            "format": "PNG",
            "resolution": [
                400,
                400,
            ],
            'frames': '1-2',
        }
    },
    '2_short': {
        'type': "Blender",
        'name': 'test task',
        'timeout': "0:08:00",
        "subtask_timeout": "0:07:30",
        "subtasks_count": 2,
        "bid": 1.0,
        "resources": [],
        "options": {
            "output_path": '',
            "format": "PNG",
            "resolution": [
                320,
                240
            ]
        }
    },
    'jpg': {
        'type': "Blender",
        'name': 'test task',
        'timeout': "0:10:00",
        "subtask_timeout": "0:09:50",
        "subtasks_count": 1,
        "bid": 1.0,
        "resources": [],
        "options": {
            "output_path": '',
            "format": "JPG",
            "resolution": [
                320,
                240
            ]
        }
    },
    'jpeg': {
        'type': "Blender",
        'name': 'test task',
        'timeout': "0:10:00",
        "subtask_timeout": "0:09:50",
        "subtasks_count": 1,
        "bid": 1.0,
        "resources": [],
        "options": {
            "output_path": '',
            "format": "JPEG",
            "resolution": [
                320,
                240
            ]
        }
    },
    'exr': {
        'type': "Blender",
        'name': 'test task',
        'timeout': "0:10:00",
        "subtask_timeout": "0:09:50",
        "subtasks_count": 1,
        "bid": 1.0,
        "resources": [],
        "options": {
            "output_path": '',
            "format": "EXR",
            "resolution": [
                320,
                240
            ]
        }
    },
    'gpu': {
        'type': "Blender",
        'name': 'test task',
        'timeout': "0:20:00",
        "subtask_timeout": "0:19:50",
        "subtasks_count": 1,
        "bid": 1.0,
        "resources": [],
        "options": {
            "output_path": '',
            "format": "PNG",
            "resolution": [
                320,
                240
            ]
        },
        'compute_on': 'gpu',
    },
    '4k': {
        'type': "Blender",
        'name': 'test task',
        'timeout': "0:20:00",
        "subtask_timeout": "0:19:50",
        "subtasks_count": 1,
        "bid": 1.0,
        "resources": [],
        "options": {
            "output_path": '',
            "format": "PNG",
            "resolution": [
                4096,
                2160,
            ]
        }
    },
    '3k-low-samples': {
        'type': "Blender",
        'name': 'test task',
        'timeout': "0:20:00",
        "subtask_timeout": "0:19:50",
        "subtasks_count": 1,
        "bid": 1.0,
        "resources": [],
        "options": {
            "output_path": '',
            "format": "PNG",
            "resolution": [
                3072,
                1620,
            ],
            'samples': 32,
        }
    },

}


def get_settings(key: str) -> typing.Dict[str, typing.Any]:
    return copy.deepcopy(_TASK_SETTINGS[key])
