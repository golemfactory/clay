import json
import logging
import shutil
import tempfile
import time
from pathlib import Path
from typing import List
from unittest import mock

import click
from twisted.internet.task import react
from twisted.internet.defer import ensureDeferred

from golem import database, model
from golem.apps import (
    manager as appmanager,
    load_app_from_json_file,
    AppDefinition,
)
from golem.apps.default import APPS
from golem.core.common import install_reactor
from golem.core.deferred import deferred_from_future
from golem.envs.default import register_environments
from golem.envs.docker.whitelist import Whitelist
from golem.task import envmanager, requestedtaskmanager, taskcomputer

from scripts.tempdir import fix_osx_tmpdir


fix_osx_tmpdir()


logging.basicConfig(level=logging.INFO)
TASK_TIMEOUT = 360
SUBTASK_TIMEOUT = 60


async def test_task(
        work_dir: Path,
        task_params_path: str,
        app_definition: AppDefinition,
        resources: List[str],
        max_subtasks: int,
) -> None:

    env_prerequisites = app_definition.requestor_prereq
    app_dir = work_dir / 'apps'
    app_dir.mkdir(exist_ok=True)
    app_manager = appmanager.AppManager(app_dir, False)
    app_manager.register_app(app_definition)
    app_manager.set_enabled(app_definition.id, True)

    runtime_logs_dir = work_dir / 'runtime_logs'
    runtime_logs_dir.mkdir()
    env_manager = envmanager.EnvironmentManager(runtime_logs_dir)
    # FIXME: Heavy coupled to docker, change this when adding more envs
    # https://github.com/golemfactory/golem/pull/4856#discussion_r344162862
    Whitelist.add(app_definition.requestor_prereq['image'])
    register_environments(
        work_dir=str(work_dir),
        env_manager=env_manager,
        dev_mode=True,
    )

    rtm_work_dir = work_dir / 'rtm'
    rtm_work_dir.mkdir()
    rtm = requestedtaskmanager.RequestedTaskManager(
        env_manager,
        app_manager,
        public_key=b'',
        root_path=rtm_work_dir,
    )

    task_computer_work_dir = work_dir / 'computer'
    task_computer_work_dir.mkdir()
    task_computer = taskcomputer.NewTaskComputer(
        env_manager,
        task_computer_work_dir,
    )

    output_dir = work_dir / 'output'
    output_dir.mkdir()
    golem_params = requestedtaskmanager.CreateTaskParams(
        app_id=app_definition.id,
        name='testtask',
        task_timeout=TASK_TIMEOUT,
        subtask_timeout=SUBTASK_TIMEOUT,
        output_directory=output_dir,
        resources=list(map(Path, resources)),
        max_subtasks=max_subtasks,
        max_price_per_hour=1,
        concent_enabled=False,
    )
    with open(task_params_path, 'r') as f:
        task_params = json.load(f)
    task_id = await rtm.create_task(golem_params, task_params)
    print('Task created', task_id)
    await deferred_from_future(rtm.init_task(task_id))
    rtm.start_task(task_id)
    print('Task started')

    assert await deferred_from_future(rtm.has_pending_subtasks(task_id))
    computing_node = \
        requestedtaskmanager.ComputingNodeDefinition(node_id='id', name='test')
    while await deferred_from_future(rtm.has_pending_subtasks(task_id)):
        print('Getting next subtask')
        subtask_def = await deferred_from_future(rtm.get_next_subtask(
            task_id,
            computing_node,
        ))
        print('subtask', subtask_def)
        task_header = mock.Mock(
            task_id=task_id,
            environment=app_definition.requestor_env,
            environment_prerequisites=env_prerequisites,
            subtask_timeout=SUBTASK_TIMEOUT,
            deadline=time.time() + TASK_TIMEOUT,
        )
        ctd = {
            'subtask_id': subtask_def.subtask_id,
            'extra_data': subtask_def.params,
            'performance': 0,
            'deadline': time.time() + SUBTASK_TIMEOUT,
        }
        task_computer.task_given(task_header, ctd)
        for resource in subtask_def.resources:
            shutil.copy2(
                rtm.get_subtask_inputs_dir(task_id) / resource,
                task_computer.get_subtask_inputs_dir(),
            )
        (task_computer.get_subtask_inputs_dir().parent /
            subtask_def.subtask_id).mkdir()
        result_path = await task_computer.compute()
        print(f'result_path={result_path}')
        subtask_output_dir = rtm.get_subtask_outputs_dir(
            task_id, subtask_def.subtask_id)
        subtask_output_dir.mkdir()
        shutil.copy2(
            result_path,
            subtask_output_dir,
        )
        print('Starting verification')
        verdict = await deferred_from_future(rtm.verify(
            task_id,
            subtask_def.subtask_id,
        ))
        assert verdict
    print('Task completed')


@click.group()
def test():
    pass


async def _task(
        task_params_path,
        app_definition_path,
        resources,
        max_subtasks,
        work_dir,
        leave_work_dir,
) -> None:
    work_dir = Path(tempfile.mkdtemp(dir=work_dir))
    print('work_dir', work_dir)
    db = database.Database(
        model.db,
        fields=model.DB_FIELDS,
        models=model.DB_MODELS,
        db_dir=str(work_dir / 'database'),
    )
    try:
        await test_task(
            work_dir,
            task_params_path,
            app_definition_path,
            list(resources),
            max_subtasks,
        )
    finally:
        db.close()
        if not leave_work_dir:
            shutil.rmtree(work_dir)


@test.command()
@click.argument('app_definition_path', type=click.Path(exists=True))
@click.argument('task_params_path', type=click.Path(exists=True))
@click.option('--resources', type=click.Path(exists=True), multiple=True)
@click.option('--max-subtasks', type=click.INT, default=2)
@click.option('--workdir', type=click.Path(exists=True))
@click.option('--leave-workdir', is_flag=True)
def task_from_app_def(
        app_definition_path,
        task_params_path,
        resources,
        max_subtasks,
        workdir,
        leave_workdir,
):
    install_reactor()
    app_definition = load_app_from_json_file(Path(app_definition_path))
    return react(
        lambda _reactor: ensureDeferred(
            _task(
                task_params_path,
                app_definition,
                resources,
                max_subtasks,
                workdir,
                leave_workdir,
            )
        )
    )


@test.command()
@click.argument('app_id', type=click.STRING)
@click.argument('task_params_path', type=click.Path(exists=True))
@click.option('--resources', type=click.Path(exists=True), multiple=True)
@click.option('--max-subtasks', type=click.INT, default=2)
@click.option('--workdir', type=click.Path(exists=True))
@click.option('--leave-workdir', is_flag=True)
def task_from_app_id(
        app_id,
        task_params_path,
        resources,
        max_subtasks,
        workdir,
        leave_workdir,
):
    app_definition = APPS.get(app_id)
    if app_definition is None:
        available_apps = {app.name: app_id for app_id, app in APPS.items()}
        print(
            'ERROR: Invalid app_id provided. '
            f'id={app_id}, available={available_apps}'
        )
        return
    install_reactor()
    return react(
        lambda _reactor: ensureDeferred(
            _task(
                task_params_path,
                app_definition,
                resources,
                max_subtasks,
                workdir,
                leave_workdir,
            )
        )
    )


if __name__ == '__main__':
    test()
