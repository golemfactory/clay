from pathlib import Path
from unittest import mock

from golem.resource.client import DummyClient, ClientOptions
from golem.resource.resourcemanager import ResourceManager, ResourceId
from golem.testutils import TempDirFixture


class TestResourceManager(TempDirFixture):
    # pylint: disable=no-member

    def setUp(self):
        super().setUp()
        with mock.patch.object(ResourceManager, "Client", DummyClient):
            self.resource_manager = ResourceManager(
                port=1000, host='127.0.0.1')

    def test_types(self):
        assert isinstance(ResourceId("0x0"), str)

    def test_build_client_options(self):
        assert isinstance(
            ResourceManager.build_client_options(),
            ClientOptions)

    def test_share(self):
        sample_path = self.new_path / "sample.txt"

        result = self.resource_manager.share(sample_path).result
        assert isinstance(result, str)
        assert self.resource_manager._cache[sample_path] == result

    def test_share_cached(self):
        sample_path = self.new_path / "sample.txt"

        with mock.patch.object(
            self.resource_manager._client,
            'add_async',
            wraps=self.resource_manager._client.add_async
        ) as add_async:
            # First upload
            self.resource_manager.share(sample_path)
            assert add_async.call_count == 1
            # Second upload (cache lookup)
            self.resource_manager.share(sample_path)
            assert add_async.call_count == 1

    def test_download(self):
        sample_path = self.new_path / "sample.txt"
        sample_dir = self.new_path / "directory"

        sample_path.touch()

        with mock.patch.object(
            self.resource_manager._client, 'get_async',
            wraps=self.resource_manager._client.get_async
        ):
            resource_id = self.resource_manager.share(sample_path).result
            path = self.resource_manager.download(
                resource_id, sample_dir).result

            assert isinstance(path, Path)
            assert path == sample_dir / "sample.txt"

    def test_drop(self):
        sample_path = self.new_path / "sample.txt"

        with mock.patch.object(
            self.resource_manager._client, 'cancel_async',
            wraps=self.resource_manager._client.cancel_async
        ):
            resource_id = self.resource_manager.share(sample_path).result
            assert sample_path in self.resource_manager._cache

            self.resource_manager.drop(resource_id)
            assert sample_path not in self.resource_manager._cache
