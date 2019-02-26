import json
import math
import os
import time

from pathlib import Path

from . import utils


def get_subtask(
        work_dir: Path,
        resources_dir: Path,
        network_resources_dir: Path):
    with open(work_dir / 'task_params.json', 'r') as f:
        params = json.load(f)
    db = utils.get_db_connection(work_dir)
    subtask_num = utils.get_next_pending_subtask(db)
    if subtask_num is None:
        raise Exception('No available subtasks at the moment')
    print(f'Subtask number: {subtask_num}')
    utils.set_subtask_status(db, subtask_num, utils.SubtaskStatus.COMPUTING)
    db.close()

    all_frames = utils.string_to_frames(params['frames'])

    scene_file = os.path.basename(params['resources'][0])  # noqa FIXME find correct scene file

    frames, parts = _choose_frames(
        all_frames,
        subtask_num,
        params['subtasks_count'],
    )
    min_y = (subtask_num % parts) / parts
    max_y = (subtask_num % parts + 1) / parts

    subtask_id = f'{subtask_num}-{int(time.time())}'  # TODO better unique name?
    print(f'Creating subtask {subtask_id}')

    extra_data = {
        "scene_file": scene_file,
        "resolution": params['resolution'],
        "use_compositing": False,
        "samples": 0,
        "frames": frames,
        "output_format": params['format'],
        "borders": [0.0, min_y, 1.0, max_y],

        "resources": [0],
    }

    with open(work_dir / f'subtask{subtask_id}.json', 'w') as f:
        json.dump(extra_data, f)

    return subtask_id


def _choose_frames(frames, start_task, total_tasks):
    if total_tasks <= len(frames):
        subtasks_frames = int(math.ceil(len(frames) / total_tasks))
        start_frame = (start_task - 1) * subtasks_frames
        end_frame = min(start_task * subtasks_frames, len(frames))
        return frames[start_frame:end_frame], 1
    else:
        parts = max(1, int(total_tasks / len(frames)))
        return [frames[int((start_task - 1) / parts)]], parts
