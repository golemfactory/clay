from golem.task.acl import get_acl, DENY_LIST_NAME, ALL_EXCEPT_ALLOWED
from golem.testutils import TempDirFixture


class TestAcl(TempDirFixture):
    def test_no_file(self):
        acl = get_acl(self.new_path)
        assert acl._deny_set == set()
        assert acl.is_allowed("some node")

    def test_file_empty(self):
        (self.new_path / DENY_LIST_NAME).touch()
        acl = get_acl(self.new_path)
        assert acl._deny_set == set()

    def test_deny(self):
        (self.new_path / DENY_LIST_NAME).write_text(
            "Node1 \nNode2\nNode3\n\tNode4 ")

        acl = get_acl(self.new_path)
        assert acl._deny_set == {"Node1", "Node2", "Node3", "Node4"}

        assert not acl.is_allowed("Node1")
        assert acl.is_allowed("some other node")

    def test_allow(self):
        (self.new_path / DENY_LIST_NAME).write_text(
            "{}\nNode1 \nNode2\nNode3\n\tNode4 ".format(ALL_EXCEPT_ALLOWED))

        acl = get_acl(self.new_path)
        assert acl._allow_set == {"Node1", "Node2", "Node3", "Node4"}

        assert acl.is_allowed("Node1")
        assert not acl.is_allowed("some other node")
