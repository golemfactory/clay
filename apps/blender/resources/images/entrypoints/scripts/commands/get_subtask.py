from pathlib import Path
from typing import List
import json

from . import utils


def get_subtask(
        work_dir: Path,
        resources_dir: Path,
        network_resources_dir: Path):
    with open(work_dir / 'task_params.json', 'r') as f:
        task_params = json.load(f)
    db = utils.get_db_connection(work_dir)
    subtask_num = utils.get_next_pending_subtask(db)
    if subtask_num is None:
        raise Exception('No available subtasks at the moment')
    print(f'Subtask number: {subtask_num}')
    utils.set_subtask_status(db, subtask_num, utils.SubtaskStatus.COMPUTING)
    db.close()

    all_frames = utils.string_to_frames(task_params['frames'])

    frames, parts = _choose_frames(
        all_frames,
        subtask_num,
        task_params['subtasks_count'],
    )
    min_y = (subtask_num % parts) / parts
    max_y = (subtask_num % parts + 1) / parts

    subtask_id = utils.gen_subtask_id(subtask_num)
    print(f'Creating subtask {subtask_id}')

    subtask_params = {
        "scene_file": task_params['scene_file'],
        "resolution": task_params['resolution'],
        "use_compositing": False,
        "samples": 0,
        "frames": frames,
        "output_format": task_params['format'],
        "borders": [0.0, min_y, 1.0, max_y],

        "resources": [0],
    }

    with open(work_dir / f'subtask{subtask_id}.json', 'w') as f:
        json.dump(subtask_params, f)

    return subtask_id


def _choose_frames(
        frames: List[str],
        subtask_num: int,
        total_subtasks: int) -> List[str]:
    if total_subtasks > len(frames):
        parts = total_subtasks // len(frames)
        return [frames[subtask_num // parts]], parts
    frames_per_subtask = (len(frames) + total_subtasks - 1) // total_subtasks
    start_frame = subtask_num * frames_per_subtask
    end_frame = min(start_frame + frames_per_subtask, len(frames))
    return frames[start_frame:end_frame], 1
