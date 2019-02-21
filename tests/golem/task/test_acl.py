from freezegun import freeze_time

from golem.task.acl import get_acl, DENY_LIST_NAME, ALL_EXCEPT_ALLOWED, \
    DenyReason
from golem.testutils import TempDirFixture


class TestAcl(TempDirFixture):
    def test_no_file(self):
        acl = get_acl(self.new_path)
        assert acl._deny_deadlines == dict()
        self.assertEqual((True, None),
                         acl.is_allowed("some node"))

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

        self.assertEqual((False, DenyReason.blacklisted),
                         acl.is_allowed("Node1"))
        self.assertEqual((True, None),
                         acl.is_allowed("some other node"))

    def test_deny_always(self):
        acl = get_acl(self.new_path)

        assert acl.is_allowed("Node1")[0]
        assert acl.is_allowed("Node2")[0]

        acl.disallow("Node1")
        # should not throw
        acl.disallow("Node1")
        acl.disallow("Node1", 5)

        assert acl.is_allowed("Node1") == (False, DenyReason.blacklisted)
        assert acl.is_allowed("Node2") == (True, None)

    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_deny_timeout(frozen_time, self):
        acl = get_acl(self.new_path)

        acl.disallow("Node1", timeout_seconds=10)
        self.assertEqual((False, DenyReason.temporarily_blocked),
                         acl.is_allowed("Node1"))
        assert "Node1" in acl._deny_deadlines

        frozen_time.tick(30)
        assert "Node1" in acl._deny_deadlines
        assert acl.is_allowed("Node1") == (True, None)
        assert "Node1" not in acl._deny_deadlines

    @freeze_time("2018-01-01 00:00:00")
    def test_deny_max_times(self):
        acl = get_acl(self.new_path, max_times=3)
        node_id = "Node1"

        assert acl.is_allowed(node_id) == (True, None)
        acl.disallow(node_id, timeout_seconds=10)
        assert acl.is_allowed(node_id) == (True, None)
        acl.disallow(node_id, timeout_seconds=10)
        assert acl.is_allowed(node_id) == (True, None)
        acl.disallow(node_id, timeout_seconds=10)
        assert acl.is_allowed(node_id) == \
            (False, DenyReason.temporarily_blocked)

    def test_allow(self):
        self.deny_list_path.write_text(
            "{}\nNode1 \nNode2\nNode3\n\tNode4 ".format(ALL_EXCEPT_ALLOWED))

        acl = get_acl(self.new_path)
        assert acl._allow_set == {"Node1", "Node2", "Node3", "Node4"}

        self.assertEqual((True, None),
                         acl.is_allowed("Node1"))
        self.assertEqual((False, DenyReason.not_whitelisted),
                         acl.is_allowed("some other node"))

    def test_deny_disallow_persistence(self):
        self.deny_list_path.touch()

        acl = get_acl(self.new_path)
        acl.disallow('node_id1', persist=True)
        acl.disallow('node_id2', persist=True)
        acl.disallow('node_id1', persist=True)

        saved_nodes = self.deny_list_path.read_text().split()
        self.assertEqual(sorted(saved_nodes), ['node_id1', 'node_id2'])
        self.assertEqual((False, DenyReason.blacklisted),
                         acl.is_allowed("node_id1"))
        self.assertEqual((False, DenyReason.blacklisted),
                         acl.is_allowed("node_id2"))
        self.assertEqual((True, None),
                         acl.is_allowed("node_id3"))

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

        self.assertEqual((False, DenyReason.not_whitelisted),
                         acl.is_allowed("node_id1"))
        self.assertEqual((True, None),
                         acl.is_allowed("node_id2"))
        self.assertEqual((False, DenyReason.not_whitelisted),
                         acl.is_allowed("node_id3"))
