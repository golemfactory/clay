import unittest


from golem.network.transport.message import MessageRewardPaid, MessageWantToComputeTask


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

    def test_message_want_to_copmute_task(self):
        m = MessageWantToComputeTask()
        self.assertIsInstance(m, MessageWantToComputeTask)
        m = MessageWantToComputeTask("ABC", "xyz", 1000, 20, 4, 5, 3)
        self.assertEqual(m.node_name, "ABC")
        self.assertEqual(m.task_id, "xyz")
        self.assertEqual(m.perf_index, 1000)
        self.assertEqual(m.max_resource_size, 4)
        self.assertEqual(m.max_memory_size, 5)
        self.assertEqual(m.price, 20)
        self.assertEqual(m.num_cores, 3)
        self.assertEqual(m.get_type(), MessageWantToComputeTask.Type)
        dict_repr = m.dict_repr()
        m2 = MessageWantToComputeTask(dict_repr=dict_repr)
        self.assertEqual(m2.task_id, m.task_id)
        self.assertEqual(m2.node_name, m.node_name)
        self.assertEqual(m2.perf_index, m.perf_index)
        self.assertEqual(m2.max_resource_size, m.max_resource_size)
        self.assertEqual(m2.max_memory_size, m.max_memory_size)
        self.assertEqual(m2.price, m.price)
        self.assertEqual(m2.num_cores, m.num_cores)
        self.assertEqual(m.get_type(), m2.get_type())
