import os
from golem.task.deny import get_deny_set, DENY_LIST_NAME
from golem.testutils import TempDirFixture


class TestDeny(TempDirFixture):
    def test_get_deny_set(self):
        assert get_deny_set(self.path) == set()
        assert get_deny_set(self.path, "newdenylist") == set()
        open(os.path.join(self.path, DENY_LIST_NAME), 'w').close()
        assert get_deny_set(self.path) == set()
        with open(os.path.join(self.path, DENY_LIST_NAME), 'w') as f:
            f.write("Node1 \n")
            f.write("Node2\nNode3\n\tNode4 ")
        assert get_deny_set(self.path) == {"Node1", "Node2", "Node3", "Node4"}
        with open(os.path.join(self.path, "newdenylist"), 'w') as f:
            f.write("abcde\ndefgh\nijkl")
        assert get_deny_set(self.path, "newdenylist") == {"abcde",
                                                          "defgh",
                                                          "ijkl"}
