from pathlib import Path
from typing import List
from unittest import mock
import click
import json
import logging
import shutil
import tempfile
import time

from golem import app_manager as appmanager, database, model
from golem.core.common import install_reactor
from golem.core.deferred import deferred_from_future
from golem.task import envmanager, requestedtaskmanager, taskcomputer
from golem.task.task_api import docker
from golem.envs.auto_setup import auto_setup
from golem.envs.docker import cpu, whitelist

from twisted.internet.task import react
from twisted.internet.defer import ensureDeferred

logging.basicConfig(level=logging.INFO)


async def test_task(
        work_dir: Path,
        environment: str,
        env_prerequisites_json: str,
        task_params_path: Path,
        resources: List[Path],
        max_subtasks: int,
) -> None:
    env_prerequisites = json.loads(env_prerequisites_json)

    app_manager = appmanager.AppManager()
    app_name = 'test_app'
    app_manager.register_app(appmanager.AppDefinition(
        name=app_name,
        requestor_env=environment,
        requestor_prereq=env_prerequisites,
        max_benchmark_score=1.0,
    ))
    app_manager.set_enabled(app_name, True)

    env_manager = envmanager.EnvironmentManager()
    docker_cpu_config = cpu.DockerCPUConfig(work_dirs=[work_dir])
    docker_cpu_env = auto_setup(cpu.DockerCPUEnvironment(docker_cpu_config))
    docker_image = cpu.DockerCPUEnvironment.parse_prerequisites(
        env_prerequisites).image
    whitelist.Whitelist.add(docker_image)
    env_manager.register_env(
        docker_cpu_env,
        cpu.DOCKER_CPU_METADATA,
        docker.DockerTaskApiPayloadBuilder,
    )
    env_manager.set_enabled(cpu.DOCKER_CPU_METADATA.id, True)

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
        app_id=app_name,
        name='testtask',
        task_timeout=3600,
        subtask_timeout=3600,
        output_directory=output_dir,
        resources=resources,
        max_subtasks=max_subtasks,
        max_price_per_hour=1,
        concent_enabled=False,
    )
    with open(task_params_path, 'r') as f:
        task_params = json.load(f)
    task_id = rtm.create_task(golem_params, task_params)
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
            environment=environment,
            environment_prerequisites=env_prerequisites,
            subtask_timeout=3600,
            deadline=time.time() + 3600,
        )
        ctd = {
            'subtask_id': subtask_def.subtask_id,
            'extra_data': subtask_def.params,
            'performance': 0,
            'deadline': time.time() + 3600,
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
        shutil.copy2(
            result_path,
            rtm.get_subtask_outputs_dir(task_id),
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
        environment,
        env_prerequisites,
        task_params_path,
        resource,
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
            environment,
            env_prerequisites,
            task_params_path,
            list(resource),
            max_subtasks,
        )
    finally:
        db.close()
        if not leave_work_dir:
            shutil.rmtree(work_dir)


@test.command()
@click.argument('environment', type=click.STRING)
@click.argument('env_prerequisites', type=click.STRING)
@click.argument('task_params_path', type=click.Path(exists=True))
@click.option('--resource', type=click.Path(exists=True), multiple=True)
@click.option('--max-subtasks', type=click.INT, default=2)
@click.option('--workdir', type=click.Path(exists=True))
@click.option('--leave-workdir', is_flag=True)
def task(
        environment,
        env_prerequisites,
        task_params_path,
        resource,
        max_subtasks,
        workdir,
        leave_workdir,
):
    install_reactor()
    return react(
        lambda _reactor: ensureDeferred(
            _task(
                environment,
                env_prerequisites,
                task_params_path,
                resource,
                max_subtasks,
                workdir,
                leave_workdir,
            )
        )
    )


if __name__ == '__main__':
    test()
