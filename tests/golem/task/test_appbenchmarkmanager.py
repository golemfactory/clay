# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# ^^ Pytest fixtures in the same file require the same name
from pathlib import Path

from mock import patch, MagicMock
import pytest

from golem.envs import Environment, EnvMetadata
from golem.model import AppBenchmark
from golem.task.benchmarkmanager import AppBenchmarkManager
from golem.task.envmanager import EnvironmentManager
from golem.task.exceptions import ComputationInProgress
from golem.task.task_api import TaskApiPayloadBuilder
from golem.testutils import pytest_database_fixture  # noqa pylint: disable=unused-import
from tests.utils.asyncio import AsyncMock

PACKAGE = 'golem.task.benchmarkmanager'

ENV_ID = 'env'
ENV_PREREQ_DICT = dict(key='value')
PREREQ_HASH = '0xdeadbeef'


@pytest.mark.usefixtures('pytest_database_fixture')
class TestAppBenchmarkManager:

    def setup_env(self, env_id):
        env = MagicMock(spec=Environment)
        metadata = EnvMetadata(id=env_id)
        payload_builder = MagicMock(spec_set=TaskApiPayloadBuilder)
        self.env_manager.register_env(env, metadata, payload_builder)
        return env, metadata, payload_builder

    @pytest.fixture(autouse=True)
    def setup_method(self, tmpdir, event_loop):
        # pylint: disable=attribute-defined-outside-init
        self.env_manager = EnvironmentManager()
        self.app_benchmark_manager = AppBenchmarkManager(
            env_manager=self.env_manager,
            root_path=Path(tmpdir))
        self.setup_env(ENV_ID)

    @pytest.mark.asyncio
    async def test_get_benchmark_score_existing(self):
        self.app_benchmark_manager._run_benchmark = AsyncMock(return_value=10.)

        app_benchmark = AppBenchmark(hash=PREREQ_HASH, score=1000.)
        app_benchmark.save()

        with patch(f'{PACKAGE}.hash_prereq_dict', return_value=PREREQ_HASH):
            score = await self.app_benchmark_manager.get_benchmark_score(
                env_id=ENV_ID,
                env_prereq_dict=ENV_PREREQ_DICT)

        assert not self.app_benchmark_manager._run_benchmark.called
        assert score == 1000.

    @pytest.mark.asyncio
    async def test_get_benchmark_score_new(self):
        self.app_benchmark_manager._run_benchmark = AsyncMock(return_value=10.)

        app_benchmark = AppBenchmark(hash=f"{PREREQ_HASH}ff", score=1000.)
        app_benchmark.save()

        with patch(f'{PACKAGE}.hash_prereq_dict', return_value=PREREQ_HASH):
            score = await self.app_benchmark_manager.get_benchmark_score(
                env_id=ENV_ID,
                env_prereq_dict=ENV_PREREQ_DICT)

        assert self.app_benchmark_manager._run_benchmark.called
        assert score == 10.

    @pytest.mark.asyncio
    async def test_get_benchmark_score_exception(self):
        self.app_benchmark_manager._run_benchmark = AsyncMock(return_value=10.)
        self.app_benchmark_manager._computing = True

        try:
            await self.app_benchmark_manager.get_benchmark_score(
                env_id=ENV_ID,
                env_prereq_dict=ENV_PREREQ_DICT)
        except ComputationInProgress:
            pass
        else:
            raise RuntimeError("Computation should have failed")

        assert not self.app_benchmark_manager._run_benchmark.called

    @pytest.mark.asyncio
    async def test_run_benchmark(self):
        create = AsyncMock()
        create.return_value = create

        with patch(f'{PACKAGE}.ProviderAppClient.create', create):
            with patch(f'{PACKAGE}.hash_prereq_dict', return_value=PREREQ_HASH):
                shared_dir = self.app_benchmark_manager._root_path / PREREQ_HASH
                await self.app_benchmark_manager._run_benchmark(
                    ENV_ID,
                    ENV_PREREQ_DICT)

                assert create.called
                assert create.run_benchmark.called
                assert shared_dir.exists()

    def test_remove_benchmark_scores(self):
        app_benchmark = AppBenchmark(hash=PREREQ_HASH, score=1000.)
        app_benchmark.save()

        assert len(list(app_benchmark.select().execute())) == 1
        self.app_benchmark_manager.remove_benchmark_scores()
        assert not list(app_benchmark.select().execute())
