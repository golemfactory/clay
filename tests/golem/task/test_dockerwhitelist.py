from golem.task.docker_whitelist import DockerWhitelist

from golem.testutils import DatabaseFixture


class TestDockerWhitelist(DatabaseFixture):
    def test_simple_flow(self):
        repo = 'test_repo'
        assert not DockerWhitelist.is_whitelisted(repo)

        DockerWhitelist.add(repo)
        assert DockerWhitelist.is_whitelisted(repo)

        DockerWhitelist.remove(repo)
        assert not DockerWhitelist.is_whitelisted(repo)

    def test_double_add_remove(self):
        repo = 'test_repo'
        assert DockerWhitelist.add(repo)
        assert not DockerWhitelist.add(repo)

        assert DockerWhitelist.remove(repo)
        assert not DockerWhitelist.remove(repo)
