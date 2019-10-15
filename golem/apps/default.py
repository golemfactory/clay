import logging
from pathlib import Path
from typing import List, Optional

from golem_task_api.envs import DOCKER_CPU_ENV_ID
from pathvalidate import sanitize_filename

from golem.apps import AppId
from golem.apps.manager import AppDefinition

logger = logging.getLogger(__name__)


BlenderAppDefinition_v0_3_0 = AppDefinition(
    name='golemfactory/blenderapp',
    author='Golem Factory GmbH',
    license='GPLv3',
    version='0.3.0',
    description=(
        'Rendering with Blender, the free and open source '
        '3D creation suite'
    ),

    requestor_env=DOCKER_CPU_ENV_ID,
    requestor_prereq=dict(
        image='golemfactory/blenderapp',
        tag='0.3.0',
    ),

    max_benchmark_score=10000.,
)


def _save_app_definition(
        path: Path,
        app_definition: AppDefinition
) -> Optional[AppId]:
    filename = f"{app_definition.name}_{app_definition.version}.json"
    filename = sanitize_filename(filename, replacement_text="_")

    destination_path = path / filename
    if not destination_path.exists():
        logger.info(
            f'Saving built-in app "{app_definition.name}" '
            f'definition to {destination_path}')

        with open(destination_path, 'w') as definition_file:
            definition_file.write(app_definition.to_json())

    return app_definition.id


def save_built_in_app_definitions(path: Path) -> List[AppId]:
    path.mkdir(parents=True, exist_ok=True)
    return [
        _save_app_definition(path, BlenderAppDefinition_v0_3_0),
    ]
