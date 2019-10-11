# pylint: disable=protected-access

import unittest
from freezegun import freeze_time

from golem.task.acl import get_acl, \
    DenyReason, AclRule, setup_acl, _DenyAcl, _AllowAcl
from golem.model import ACLAllowedNodes, ACLDeniedNodes
from golem.testutils import DatabaseFixture


class TestAcl(DatabaseFixture):

    def setUp(self):
        super().setUp()
        self.client = unittest.mock.MagicMock()
        self.client.p2pservice.incoming_peers = {
            'Node1': {
                'node_id': 'Node1',
                'node_name': 'Node1',
                'address': '34.107.145.130'
            },
            'Node2': {
                'node_id': 'Node2',
                'node_name': 'Node2',
                'address': '122.32.144.197'
            },
            'Node3': {
                'node_id': 'Node3',
                'node_name': 'Node3',
                'address': '175.5.104.123'
            },
            'Node4': {
                'node_id': 'Node4',
                'node_name': 'Node4',
                'address': '92.212.33.20'
            },
            'Node5': {
                'node_id': 'Node5',
                'node_name': 'Node5',
                'address': '23.62.179.16'
            }
        }

    def test_no_file(self):
        acl = get_acl(self.client)
        assert acl._deny_deadlines == dict()
        self.assertEqual((True, None),
                         acl.is_allowed("some node"))

    def database_empty(self):
        acl = get_acl(self.client)
        assert acl._deny_deadlines == dict()

    def test_deny(self):

        node_1 = ACLDeniedNodes(node_id="node_1", node_name="node_1")
        node_1.save()

        acl = get_acl(self.client)
        keys = set(acl._deny_deadlines.keys())
        assert keys == {"node_1"}

        self.assertEqual((False, DenyReason.blacklisted),
                         acl.is_allowed("node_1"))
        self.assertEqual((True, None),
                         acl.is_allowed("some other node"))

    def test_deny_always(self):
        acl = get_acl(self.client)

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
        acl = get_acl(self.client)

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
            acl = get_acl(self.client)
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
        acl = setup_acl(self.client, AclRule.allow, ['Node1', 'Node3'])
        assert acl.is_allowed('Node1') == (False, DenyReason.blacklisted)
        assert acl.is_allowed('Node2') == (True, None)
        assert acl.is_allowed('Node3') == (False, DenyReason.blacklisted)

    def test_setup_new_only_allowed(self):
        acl = setup_acl(self.client, AclRule.deny, ['Node1', 'Node3'])
        assert acl.is_allowed('Node1') == (True, None)
        assert acl.is_allowed('Node2') == (False, DenyReason.not_whitelisted)
        assert acl.is_allowed('Node3') == (True, None)

    def test_setup_new_persist(self):
        acl = setup_acl(self.client, AclRule.allow, ['Node1', 'Node3'])
        assert acl.is_allowed('Node1') == (False, DenyReason.blacklisted)
        assert acl.is_allowed('Node2') == (True, None)
        assert acl.is_allowed('Node3') == (False, DenyReason.blacklisted)

        acl = setup_acl(self.client, AclRule.deny, ['Node2'])
        assert acl.is_allowed('Node1') == (False, DenyReason.not_whitelisted)
        assert acl.is_allowed('Node3') == (False, DenyReason.not_whitelisted)
        assert acl.is_allowed('Node2') == (True, None)

    def test_DenyAcl_no_exceptions(self):
        acl = _DenyAcl(self.client)
        assert acl.status().default_rule == AclRule.allow
        assert not acl.status().rules
        assert acl.is_allowed('Node1') == (True, None)

    def test_AllowAcl_no_exceptions(self):
        acl = _AllowAcl(self.client)
        assert acl.status().default_rule == AclRule.deny
        assert not acl.status().rules
        assert acl.is_allowed('Node1') == (False, DenyReason.not_whitelisted)

    def test_deny_max_times(self):
        with freeze_time('2016-09-29 18:18:01') as frozen_time:
            acl = get_acl(self.client, max_times=3)
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
            self.assertCountEqual([node['node_id']
                                   for node in disallowed_nodes], [node_id])

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
        allowed_node_list = [
            ACLDeniedNodes(node_id="Node1", node_name="Node1").to_dict(),
            ACLDeniedNodes(node_id="Node2", node_name="Node2").to_dict(),
            ACLDeniedNodes(node_id="Node3", node_name="Node3").to_dict(),
            ACLDeniedNodes(node_id="Node4", node_name="Node4").to_dict()
        ]
        ACLAllowedNodes.insert_many(allowed_node_list).execute()

        acl = setup_acl(self.client, AclRule.deny, [])
        acl.allow('Node5', persist=True)
        acl.disallow('Node4', persist=True)

        allowed_nodes = [r[0] for r in acl.status().rules]
        self.assertCountEqual(
            [node['node_id'] for node in allowed_nodes],
            ["Node1", "Node2", "Node3", "Node5"]
        )

        saved_nodes = ACLAllowedNodes.select().execute()
        self.assertCountEqual(
            [node.node_id for node in saved_nodes],
            ["Node1", "Node2", "Node3", "Node5"]
        )

        self.assertEqual((True, None),
                         acl.is_allowed("Node1"))
        self.assertEqual((False, DenyReason.not_whitelisted),
                         acl.is_allowed("some other node"))

    def test_deny_disallow_allow_persistence(self):
        node_4 = ACLDeniedNodes(node_id='Node4', node_name='Node4')
        node_4.save()

        acl = get_acl(self.client)
        acl.disallow('Node1', persist=True)
        acl.disallow('Node2', persist=True)
        acl.disallow('Node1', persist=True)
        acl.allow('Node1')
        acl.allow('Node4', persist=True)

        disallowed_nodes = [r[0] for r in acl.status().rules]
        self.assertCountEqual([node['node_id']
                               for node in disallowed_nodes], ['Node2'])

        saved_nodes = ACLDeniedNodes.select()
        self.assertCountEqual(
            [node.node_id for node in saved_nodes], ['Node1', 'Node2'])

        self.assertEqual((True, None),
                         acl.is_allowed("Node1"))
        self.assertEqual((False, DenyReason.blacklisted),
                         acl.is_allowed("Node2"))
        self.assertEqual((True, None),
                         acl.is_allowed("Node3"))

    def test_allow_disallow_persistence(self):

        acl = setup_acl(self.client, AclRule.deny, ['Node1', 'Node2'])

        acl.disallow('Node1', persist=True)
        acl.disallow('Node3', persist=True)
        acl.disallow('Node1', persist=True)
        acl.allow('Node4')

        allowed_nodes = [r[0] for r in acl.status().rules]
        self.assertCountEqual(
            [node['node_id'] for node in allowed_nodes], ['Node2', 'Node4'])

        # Node which is not in p2pservice incoming peer list
        acl.allow('Node6')

        allowed_nodes = [r[0] for r in acl.status().rules]
        self.assertCountEqual([node['node_id'] for node in allowed_nodes],
                              ['Node2', 'Node4', 'Node6'])

        saved_allowed_nodes = ACLAllowedNodes.select().execute()
        self.assertCountEqual([node.node_id for node in saved_allowed_nodes],
                              ['Node2'])

        self.assertEqual((False, DenyReason.not_whitelisted),
                         acl.is_allowed("Node1"))
        self.assertEqual((True, None),
                         acl.is_allowed("Node2"))
        self.assertEqual((False, DenyReason.not_whitelisted),
                         acl.is_allowed("Node3"))
        self.assertEqual((True, None),
                         acl.is_allowed("Node4"))

    def test_allow_disallow_ip_persistence(self):
        # Test for IP which  is exist in p2pservice incoming peer list
        acl = setup_acl(self.client, AclRule.deny,
                        ['122.32.144.197', '34.107.145.130'])
        self.assertEqual((True, None),
                         acl.is_allowed("34.107.145.130"))
        allowed_ips = [r[0] for r in acl.status().rules]
        self.assertCountEqual(
            [node['node_name'] for node in allowed_ips], ['Node1', 'Node2'])
        # Test for IP which doesn't exist in p2pservice incoming peer list
        acl.allow('4.247.45.93', persist=True)
        allowed_ips = [r[0] for r in acl.status().rules]
        self.assertCountEqual([node['node_name'] for node in allowed_ips],
                              ['Node2', 'Node1', None])
        # Remove uknown IP
        acl.disallow('4.247.45.93', persist=True)
        allowed_ips = [r[0] for r in acl.status().rules]
        self.assertCountEqual(
            [node['node_name'] for node in allowed_ips], ['Node1', 'Node2'])
        # Remove known IP
        acl.disallow('34.107.145.130', persist=True)
        allowed_ips = [r[0] for r in acl.status().rules]
        self.assertCountEqual(
            [node['node_name'] for node in allowed_ips], ['Node2'])
