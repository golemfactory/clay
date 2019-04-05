from golem.task.docker_whitelist import DockerWhitelist

from golem.testutils import DatabaseFixture


class TestDockerWhitelist(DatabaseFixture):
    def test_simple_flow(self):
        repo = 'test_repo'
        image = f'{repo}/image'
        assert not DockerWhitelist.is_whitelisted(image)

        DockerWhitelist.add(repo)
        assert DockerWhitelist.is_whitelisted(image)

        DockerWhitelist.remove(repo)
        assert not DockerWhitelist.is_whitelisted(image)

    def test_double_add_remove(self):
        repo = 'test_repo'
        assert DockerWhitelist.add(repo)
        assert not DockerWhitelist.add(repo)

        assert DockerWhitelist.remove(repo)
        assert not DockerWhitelist.remove(repo)
