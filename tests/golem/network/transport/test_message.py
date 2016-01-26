import unittest


from golem.network.transport.message import MessageRewardPaid


class TestMessages(unittest.TestCase):
    def test_message_reward_paid(self):
        m = MessageRewardPaid()
        self.assertIsInstance(m, MessageRewardPaid)
        m = MessageRewardPaid("ABC", 232)

        self.assertEqual(m.task_id, "ABC")
        self.assertEqual(m.reward, 232)
        dict_repr = m.dict_repr()
        m2 = MessageRewardPaid(dict_repr=dict_repr)
        self.assertEqual(m.task_id, m2.task_id)
        self.assertEqual(m.reward, m2.reward)
