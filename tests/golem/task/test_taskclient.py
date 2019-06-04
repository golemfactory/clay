import unittest
import uuid

from golem.task.taskclient import TaskClient


class TestTaskClient(unittest.TestCase):
    def test(self):

        node_id = str(uuid.uuid4())
        node_dict = {}

        # when
        tc = TaskClient.assert_exists(node_id, node_dict)

        # then
        assert tc
        assert node_id in node_dict

        assert not tc.should_wait(b'the hash')
        assert not tc.rejected()
        assert tc._started == 0
        assert tc._accepted == 0

        # when
        assert tc.start(wtct_hash=b'the hash', num_subtasks=3)

        # then
        assert not tc.should_wait(b'the hash')
        assert tc.should_wait(b'other hash')
        assert tc.should_wait()
        assert not tc.rejected()
        assert tc._wtct_hash == b'the hash'
        assert tc._wtct_num_subtasks == 3
        assert tc._started == 1
        assert tc._accepted == 0

        # do not allow to start other WTCT
        assert not tc.start(wtct_hash=b'other hash', num_subtasks=7)

        # when
        assert tc.start(wtct_hash=b'the hash', num_subtasks=3)

        # then
        assert not tc.should_wait(b'the hash')
        assert not tc.rejected()
        assert tc._started == 2
        assert tc._accepted == 0

        # when
        assert tc.start(wtct_hash=b'the hash', num_subtasks=3)

        # then
        assert tc.should_wait(b'the hash')
        assert not tc.rejected()
        assert tc._started == 3
        assert tc._accepted == 0

        # do not allow to start more (4) subtasks than requested (3)
        assert not tc.start(wtct_hash=b'the hash', num_subtasks=3)
        # ... nor other WTCT
        assert not tc.start(wtct_hash=b'other hash', num_subtasks=7)

        # then
        assert tc.should_wait(b'the hash')
        assert not tc.rejected()
        assert tc._started == 3
        assert tc._accepted == 0

        # when cancel single subtask
        tc.cancel()

        # then
        assert not tc.should_wait(b'the hash')
        assert not tc.rejected()
        assert tc._started == 2
        assert tc._accepted == 0

        # when
        assert tc.start(wtct_hash=b'the hash', num_subtasks=3)

        # then
        assert tc.should_wait(b'the hash')
        assert not tc.rejected()
        assert tc._started == 3
        assert tc._accepted == 0

        # when
        tc.accept()

        # then
        assert tc.should_wait(b'the hash')
        assert tc.should_wait(b'other hash')
        assert tc.should_wait()
        assert not tc.rejected()
        assert tc._started == 3
        assert tc._accepted == 1

        # when
        tc.accept()

        # then
        assert tc.should_wait(b'the hash')
        assert tc.should_wait(b'other hash')
        assert tc.should_wait()
        assert not tc.rejected()
        assert tc._started == 3
        assert tc._accepted == 2

        # when -- last subtask accepted
        tc.accept()

        # then
        assert not tc.should_wait(b'the hash')
        assert not tc.should_wait(b'other hash')
        assert not tc.should_wait()
        assert not tc.rejected()
        assert tc._started == 0
        assert tc._accepted == 0

        # now allow to start other WTCT
        assert tc.start(wtct_hash=b'other hash', num_subtasks=7)

        tc.reject()
        assert tc.rejected()
