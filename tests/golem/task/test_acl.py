# pylint: disable=protected-access

from freezegun import freeze_time

from golem.task.acl import get_acl, DENY_LIST_NAME, ALL_EXCEPT_ALLOWED, \
    DenyReason, AclRule, setup_acl, _DenyAcl, _AllowAcl
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

    # pylint: disable=no-self-argument
    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_deny_timeout(frozen_time, self):
        assert isinstance(self, TestAcl)
        acl = get_acl(self.new_path)

        acl.disallow("Node1", timeout_seconds=10)
        self.assertEqual((False, DenyReason.temporarily_blocked),
                         acl.is_allowed("Node1"))
        assert "Node1" in acl._deny_deadlines

        frozen_time.tick(30)  # pylint: disable=no-member
        assert "Node1" in acl._deny_deadlines
        assert acl.is_allowed("Node1") == (True, None)
        assert "Node1" not in acl._deny_deadlines

    def test_timeout_in_status(self):
        with freeze_time('2016-09-29 18:18:01') as frozen_time:
            acl = get_acl(self.new_path)
            s = acl.status()
            assert s.rules == [] and s.default_rule == AclRule.allow
            acl.disallow('Node1')
            s = acl.status()
            assert len(s.rules) == 1 and s.default_rule == AclRule.allow
            assert acl.is_allowed('Node1') == (False, DenyReason.blacklisted)
            acl.disallow('Node2', timeout_seconds=10)
            assert acl.is_allowed('Node2') == \
                (False, DenyReason.temporarily_blocked)
            assert acl.is_allowed('Node3') == (True, None)
            frozen_time.tick(5)
            assert acl.is_allowed('Node2') == \
                (False, DenyReason.temporarily_blocked)
            frozen_time.tick(5)
            assert acl.is_allowed('Node2') == (True, None)

    def test_setup_new_all_except(self):
        acl = setup_acl(None, AclRule.allow, ['Node1', 'Node3'])
        assert acl.is_allowed('Node1') == (False, DenyReason.blacklisted)
        assert acl.is_allowed('Node2') == (True, None)
        assert acl.is_allowed('Node3') == (False, DenyReason.blacklisted)

    def test_setup_new_only_allowed(self):
        acl = setup_acl(None, AclRule.deny, ['Node1', 'Node3'])
        assert acl.is_allowed('Node1') == (True, None)
        assert acl.is_allowed('Node2') == (False, DenyReason.not_whitelisted)
        assert acl.is_allowed('Node3') == (True, None)

    def test_setup_new_persist(self):
        acl = setup_acl(self.new_path, AclRule.allow, ['Node1', 'Node3'])
        assert acl.is_allowed('Node1') == (False, DenyReason.blacklisted)
        assert acl.is_allowed('Node2') == (True, None)
        assert acl.is_allowed('Node3') == (False, DenyReason.blacklisted)

        acl = get_acl(self.new_path)
        assert acl.is_allowed('Node1') == (False, DenyReason.blacklisted)
        assert acl.is_allowed('Node2') == (True, None)
        assert acl.is_allowed('Node3') == (False, DenyReason.blacklisted)

        setup_acl(self.new_path, AclRule.deny, ['Node2'])
        acl = get_acl(self.new_path)
        assert acl.is_allowed('Node1') == (False, DenyReason.not_whitelisted)
        assert acl.is_allowed('Node3') == (False, DenyReason.not_whitelisted)
        assert acl.is_allowed('Node2') == (True, None)

    def test_DenyAcl_no_exceptions(self):
        acl = _DenyAcl()
        assert acl.status().default_rule == AclRule.allow
        assert not acl.status().rules
        assert acl.is_allowed('Node1') == (True, None)

    def test_AllowAcl_no_exceptions(self):
        acl = _AllowAcl()
        assert acl.status().default_rule == AclRule.deny
        assert not acl.status().rules
        assert acl.is_allowed('Node1') == (False, DenyReason.not_whitelisted)

    def test_deny_max_times(self):
        with freeze_time('2016-09-29 18:18:01') as frozen_time:
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

            disallowed_nodes = [r[0] for r in acl.status().rules]
            self.assertCountEqual(disallowed_nodes, [node_id])

            frozen_time.tick(15)

            disallowed_nodes = [r[0] for r in acl.status().rules]
            self.assertCountEqual(disallowed_nodes, [])

            assert acl.is_allowed(node_id) == (True, None)

            acl.disallow(node_id, timeout_seconds=30)
            frozen_time.tick(5)
            acl.disallow(node_id, timeout_seconds=30)
            frozen_time.tick(5)
            acl.disallow(node_id, timeout_seconds=30)
            assert acl.is_allowed(node_id) == \
                (False, DenyReason.temporarily_blocked)
            frozen_time.tick(20)
            assert acl.is_allowed(node_id) == (True, None)
            acl.disallow(node_id, timeout_seconds=30)
            assert acl.is_allowed(node_id) == \
                (False, DenyReason.temporarily_blocked)

    def test_allow_allow_dissalow(self):
        self.deny_list_path.write_text(
            "{}\nNode1 \nNode2\nNode3\n\tNode4 ".format(ALL_EXCEPT_ALLOWED))

        acl = get_acl(self.new_path)
        acl.allow('Node5', persist=True)
        acl.disallow('Node4')

        allowed_nodes = [r[0] for r in acl.status().rules]
        self.assertCountEqual(
            allowed_nodes, ["Node1", "Node2", "Node3", "Node5"])

        saved_nodes = self.deny_list_path.read_text().split()
        self.assertCountEqual(
            saved_nodes,
            [ALL_EXCEPT_ALLOWED, "Node1", "Node2", "Node3", "Node4", "Node5"]
        )

        self.assertEqual((True, None),
                         acl.is_allowed("Node1"))
        self.assertEqual((False, DenyReason.not_whitelisted),
                         acl.is_allowed("some other node"))

    def test_deny_disallow_allow_persistence(self):
        self.deny_list_path.write_text('node_id4')

        acl = get_acl(self.new_path)
        acl.disallow('node_id1', persist=True)
        acl.disallow('node_id2', persist=True)
        acl.disallow('node_id1', persist=True)
        acl.allow('node_id1')
        acl.allow('node_id4', persist=True)

        disallowed_nodes = [r[0] for r in acl.status().rules]
        self.assertCountEqual(disallowed_nodes, ['node_id2'])

        saved_nodes = self.deny_list_path.read_text().split()
        self.assertCountEqual(saved_nodes, ['node_id1', 'node_id2'])

        self.assertEqual((True, None),
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
        acl.allow('node_id4')

        allowed_nodes = [r[0] for r in acl.status().rules]
        self.assertCountEqual(allowed_nodes, ['node_id2', 'node_id4'])

        saved_allowed_nodes = self.deny_list_path.read_text().split()
        self.assertCountEqual(saved_allowed_nodes,
                              [ALL_EXCEPT_ALLOWED, 'node_id2'])

        self.assertEqual((False, DenyReason.not_whitelisted),
                         acl.is_allowed("node_id1"))
        self.assertEqual((True, None),
                         acl.is_allowed("node_id2"))
        self.assertEqual((False, DenyReason.not_whitelisted),
                         acl.is_allowed("node_id3"))
        self.assertEqual((True, None),
                         acl.is_allowed("node_id4"))
