import json
import zipfile

from pathlib import Path

from . import utils


def create_task(
        work_dir: Path,
        resources_dir: Path,
        network_resources_dir: Path) -> None:
    with open(work_dir / 'task_params.json', 'r') as f:
        params = json.load(f)
    frame_count = len(utils.string_to_frames(params['frames']))
    subtasks_count = params['subtasks_count']
    assert subtasks_count <= frame_count or subtasks_count % frame_count == 0
    with zipfile.ZipFile(network_resources_dir / '0.zip', 'w') as zipf:
        for resource in params['resources']:
            resource_path = resources_dir / resource
            zipf.write(resource_path, resource)

    db = utils.get_db_connection(work_dir)
    utils.init_tables(db, subtasks_count)
    db.close()
