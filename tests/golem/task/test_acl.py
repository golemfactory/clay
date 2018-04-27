from freezegun import freeze_time

from golem.task.acl import get_acl, DENY_LIST_NAME, ALL_EXCEPT_ALLOWED
from golem.testutils import TempDirFixture


class TestAcl(TempDirFixture):
    def test_no_file(self):
        acl = get_acl(self.new_path)
        assert acl._deny_deadlines == dict()
        assert acl.is_allowed("some node")

    @property
    def deny_list_path(self):
        return self.new_path / DENY_LIST_NAME

    def test_file_empty(self):
        self.deny_list_path.touch()
        acl = get_acl(self.new_path)
        assert acl._deny_deadlines == dict()

    def test_deny(self):
        self.deny_list_path.write_text(
            "Node1 \nNode2\nNode3\n\tNode4 ")

        acl = get_acl(self.new_path)
        keys = set(acl._deny_deadlines.keys())
        assert keys == {"Node1", "Node2", "Node3", "Node4"}

        assert not acl.is_allowed("Node1")
        assert acl.is_allowed("some other node")

    @freeze_time("2018-01-01 00:00:00")
    def test_deny_timeout(self):
        acl = get_acl(self.new_path)

        acl.disallow("Node1", timeout_seconds=10)
        assert not acl.is_allowed("Node1")
        assert "Node1" in acl._deny_deadlines

        with freeze_time("2018-01-01 00:00:30"):
            assert "Node1" in acl._deny_deadlines
            assert acl.is_allowed("Node1")
            assert "Node1" not in acl._deny_deadlines

    def test_allow(self):
        self.deny_list_path.write_text(
            "{}\nNode1 \nNode2\nNode3\n\tNode4 ".format(ALL_EXCEPT_ALLOWED))

        acl = get_acl(self.new_path)
        assert acl._allow_set == {"Node1", "Node2", "Node3", "Node4"}

        assert acl.is_allowed("Node1")
        assert not acl.is_allowed("some other node")

    def test_deny_disallow_persistence(self):
        self.deny_list_path.touch()

        acl = get_acl(self.new_path)
        acl.disallow('node_id1', persist=True)
        acl.disallow('node_id2', persist=True)
        acl.disallow('node_id1', persist=True)

        saved_nodes = self.deny_list_path.read_text().split()
        self.assertEqual(sorted(saved_nodes), ['node_id1', 'node_id2'])

    def test_allow_disallow_persistence(self):
        self.deny_list_path.write_text('\n'.join((
            ALL_EXCEPT_ALLOWED,
            'node_id1',
            'node_id2')))

        acl = get_acl(self.new_path)
        acl.disallow('node_id1', persist=True)
        acl.disallow('node_id3', persist=True)
        acl.disallow('node_id1', persist=True)

        saved_nodes = self.deny_list_path.read_text().split()
        self.assertEqual(sorted(saved_nodes), [ALL_EXCEPT_ALLOWED, 'node_id2'])
