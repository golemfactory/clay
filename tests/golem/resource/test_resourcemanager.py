from unittest import mock

from golem.resource.client import ClientOptions
from golem.resource.resourcemanager import ResourceManager, ResourceId
from golem.testutils import TempDirFixture


class TestResourceManager(TempDirFixture):
    # pylint: disable=no-member

    def setUp(self):
        super().setUp()

        client = mock.Mock()
        client.build_options.return_value = ClientOptions("mocked", 1.0)
        client.add_async.return_value = ResourceId("0x0")
        client.get_async.return_value = ["0x0", ["mocked.file"]]

        self.resource_manager = ResourceManager(client)  # noqa
        self.client = client

    def test_types(self):
        assert isinstance(ResourceId("0x0"), str)

    def test_build_client_options(self):
        assert isinstance(
            self.resource_manager.build_client_options(),
            ClientOptions)

    def test_share(self):
        sample_path = self.new_path / "sample.txt"

        result = self.resource_manager.share(sample_path).result
        assert isinstance(result, str)
        assert self.resource_manager._cache[sample_path] == result

    def test_share_cached(self):
        sample_path = self.new_path / "sample.txt"

        # First upload
        self.resource_manager.share(sample_path)
        assert self.client.add_async.call_count == 1
        # Second upload (cache lookup)
        self.resource_manager.share(sample_path)
        assert self.client.add_async.call_count == 1

    def test_download(self):
        resource_id = ResourceId("0x0")
        sample_dir = self.new_path / "directory"
        sample_dir.mkdir(parents=True)

        self.resource_manager.download(resource_id, sample_dir)
        assert self.client.get_async.called

    def test_drop(self):
        sample_path = self.new_path / "sample.txt"

        resource_id = self.resource_manager.share(sample_path).result
        assert sample_path in self.resource_manager._cache

        self.resource_manager.drop(resource_id)
        assert sample_path not in self.resource_manager._cache
