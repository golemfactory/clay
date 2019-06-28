from golem.envs.docker.whitelist import Whitelist

from golem.testutils import DatabaseFixture


class TestWhitelist(DatabaseFixture):
    def test_simple_flow(self):
        repo = 'test_repo'
        image = f'{repo}/image'
        assert not Whitelist.is_whitelisted(image)

        Whitelist.add(repo)
        assert Whitelist.is_whitelisted(image)

        Whitelist.remove(repo)
        assert not Whitelist.is_whitelisted(image)

    def test_double_add_remove(self):
        repo = 'test_repo'
        assert Whitelist.add(repo)
        assert not Whitelist.add(repo)

        assert Whitelist.remove(repo)
        assert not Whitelist.remove(repo)
