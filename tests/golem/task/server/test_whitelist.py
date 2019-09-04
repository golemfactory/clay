import unittest
from unittest import mock

from freezegun import freeze_time

from golem.core.common import get_timestamp_utc
from golem.task.server.whitelist import DiscoveredDockerImage, \
    DockerWhitelistRPC
from golem.tools.testwithdatabase import TestWithDatabase

ROOT_PATH = 'golem.task.server.whitelist'
MAX_IMAGES = 5


class TestDiscoveredDockerImage(unittest.TestCase):

    @freeze_time("1000")
    def test_new(self):
        discovered_img = DiscoveredDockerImage(name='golemfactory/test')
        self.assertEqual(discovered_img.name, 'golemfactory/test')
        self.assertEqual(discovered_img.discovery_ts, get_timestamp_utc())
        self.assertEqual(discovered_img.last_seen_ts, get_timestamp_utc())
        self.assertEqual(discovered_img.times_seen, 1)


@mock.patch(f'{ROOT_PATH}.MAX_DISCOVERED_IMAGES', MAX_IMAGES)
@mock.patch(f'{ROOT_PATH}.EventPublisher')
class TestDiscoveryStorage(TestWithDatabase):

    def setUp(self) -> None:
        super().setUp()
        self.whitelist_rpc = DockerWhitelistRPC()

    def test_discovery_storage_limit(self, event_publisher):
        for i in range(MAX_IMAGES * 2):
            self.whitelist_rpc._docker_image_discovered(name=f'repo/{i}')

        assert event_publisher.publish.call_count == MAX_IMAGES * 2
        assert len(self.whitelist_rpc._discovered) == MAX_IMAGES

        for i in range(MAX_IMAGES):
            discovered_app = self.whitelist_rpc._discovered[i]
            assert discovered_app.name == f'repo/{MAX_IMAGES + i}'

    def test_discovered_twice(self, event_publisher):

        with freeze_time("1000"):
            initial_time = get_timestamp_utc()
            self.whitelist_rpc._docker_image_discovered(name=f'repo/0')

        assert len(self.whitelist_rpc._discovered) == 1
        discovered = self.whitelist_rpc._discovered[0]
        assert discovered.discovery_ts == initial_time
        assert discovered.last_seen_ts == initial_time
        assert discovered.times_seen == 1
        assert event_publisher.publish.call_count == 1

        with freeze_time("2000"):
            update_time = get_timestamp_utc()
            self.whitelist_rpc._docker_image_discovered(name=f'repo/0')

        assert len(self.whitelist_rpc._discovered) == 1
        discovered = self.whitelist_rpc._discovered[0]
        assert discovered.discovery_ts == initial_time
        assert discovered.last_seen_ts == update_time
        assert discovered.times_seen == 2
        assert event_publisher.publish.call_count == 1

    @mock.patch(f'{ROOT_PATH}.Whitelist.is_whitelisted', return_value=True)
    def test_discovered_when_whitelisted(self, _, event_publisher):
        for i in range(MAX_IMAGES):
            self.whitelist_rpc._docker_image_discovered(name=f'repo/{i}')

        assert event_publisher.publish.call_count == 0
        assert not self.whitelist_rpc._discovered

    @mock.patch(f'{ROOT_PATH}.Whitelist.is_whitelisted', return_value=False)
    def test_refresh(self, _, event_publisher):
        for i in range(MAX_IMAGES):
            self.whitelist_rpc._docker_image_discovered(name=f'repo/{i}')

        assert event_publisher.publish.call_count == MAX_IMAGES
        assert len(self.whitelist_rpc._discovered) == MAX_IMAGES

        def is_whitelisted(name: str) -> bool:
            return not name.startswith('test')

        with mock.patch(
            f'{ROOT_PATH}.Whitelist.is_whitelisted', side_effect=is_whitelisted
        ):
            self.whitelist_rpc._docker_image_discovered(name='test/0')

        assert len(self.whitelist_rpc._discovered) == 1


@mock.patch(f'{ROOT_PATH}.MAX_DISCOVERED_IMAGES', MAX_IMAGES)
@mock.patch(f'{ROOT_PATH}.Whitelist')
class TestAppManagerRPCMethods(TestWithDatabase):

    def setUp(self) -> None:
        super().setUp()
        self.whitelist_rpc = DockerWhitelistRPC()

        with mock.patch(f'{ROOT_PATH}.EventPublisher'):
            for i in range(MAX_IMAGES):
                self.whitelist_rpc._docker_image_discovered(name=f'repo/{i}')

    def test_docker_discovered_get(self, _):
        discovered = self.whitelist_rpc._docker_discovered_get()
        assert isinstance(discovered, dict)
        assert len(discovered) == MAX_IMAGES
        assert all(
            isinstance(key, str) and isinstance(value, dict)
            for key, value in discovered.items())

    def test_docker_whitelist_get(self, whitelist):
        self.whitelist_rpc._docker_whitelist_get()
        assert whitelist.get.call_count == 1

    def test_docker_whitelist_add(self, whitelist):
        self.whitelist_rpc._docker_refresh_discovered_images = mock.Mock()
        self.whitelist_rpc._docker_whitelist_add('repo/0')
        assert whitelist.add.call_count == 1
        assert self.whitelist_rpc._docker_refresh_discovered_images.call_count \
            == 1

    def test_docker_whitelist_remove(self, whitelist):
        self.whitelist_rpc._docker_whitelist_remove('repo/0')
        assert whitelist.remove.call_count == 1
