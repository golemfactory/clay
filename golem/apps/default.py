from pathlib import Path
from typing import List

from golem_task_api.envs import DOCKER_CPU_ENV_ID

from golem.apps import (
    AppId, AppDefinition, save_app_to_json_file, app_json_file_name,
)
from golem.marketplace import RequestorBrassMarketStrategy

BlenderAppDefinition = AppDefinition(
    name='golemfactory/blenderapp',
    author='Golem Factory GmbH',
    license='GPLv3',
    version='0.7.2',
    description=(
        'Rendering with Blender, the free and open source '
        '3D creation suite'
    ),
    requestor_env=DOCKER_CPU_ENV_ID,
    requestor_prereq=dict(
        image='golemfactory/blenderapp',
        tag='0.7.2',
    ),
    market_strategy=RequestorBrassMarketStrategy,
    max_benchmark_score=10000.,
)

APPS = {
    BlenderAppDefinition.id: BlenderAppDefinition
}


def save_built_in_app_definitions(path: Path) -> List[AppId]:
    new_app_ids = []
    for app_id, app in APPS.items():
        filename = app_json_file_name(app)
        json_file = path / filename

        if not json_file.exists():
            save_app_to_json_file(app, json_file)
            new_app_ids.append(app_id)

    return new_app_ids
