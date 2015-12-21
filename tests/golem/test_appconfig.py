import os

import golem.appconfig as appconfig

from golem.core.simpleenv import SimpleEnv
from golem.appconfig import NodeConfig, logger
from golem.tools.assertlogs import LogTestCase


class TestNodeConfig(LogTestCase):
    no_existing_name = "NOTEXISTING"
    wrong_name = "WRONGSETTINGS"
    good_name = "GOODSETTINGS"
    config_val = "1024.56"

    def setUp(self):

        not_file = SimpleEnv.env_file_name(TestNodeConfig.wrong_name)
        if not os.path.exists(not_file):
            os.makedirs(not_file)
        good_file = SimpleEnv.env_file_name(TestNodeConfig.good_name)
        with open(good_file, 'w') as f:
            f.write(TestNodeConfig.config_val)

    def test_read_estimated_performance(self):
        appconfig.ESTM_FILENAME = TestNodeConfig.no_existing_name
        with self.assertLogs(logger, level=1) as l:
            res = NodeConfig.read_estimated_performance()

        self.assertTrue(any(["Can't open" in log for log in l.output]))
        self.assertEqual(res, 0)

        appconfig.ESTM_FILENAME = TestNodeConfig.wrong_name

        not_file = SimpleEnv.env_file_name(appconfig.ESTM_FILENAME)
        with self.assertLogs(logger, level=1) as l:
            res = NodeConfig.read_estimated_performance()
        self.assertEqual(res, 0)
        self.assertTrue(any(["Can't open" in log for log in l.output]))

        appconfig.ESTM_FILENAME = TestNodeConfig.good_name
        good_file = SimpleEnv.env_file_name(appconfig.ESTM_FILENAME)
        res = NodeConfig.read_estimated_performance()
        self.assertEqual(res, "1024.6")

        with open(good_file, 'w') as f:
            f.write("1000")
        res = NodeConfig.read_estimated_performance()
        self.assertEqual(res, "1000.0")

        with open(good_file, 'w') as f:
            f.write("")
        with self.assertLogs(logger, level=1) as l:
            res = NodeConfig.read_estimated_performance()
        self.assertEqual(res, 0)
        self.assertTrue(any(["to float" in log for log in l.output]))

        with open(good_file, 'w') as f:
            f.write("abc")
        with self.assertLogs(logger, level=1) as l:
            res = NodeConfig.read_estimated_performance()
        self.assertEqual(res, 0)
        self.assertTrue(any(["to float" in log for log in l.output]))

    def tearDown(self):
        not_file = SimpleEnv.env_file_name(TestNodeConfig.wrong_name)
        if os.path.exists(not_file):
            os.removedirs(not_file)
        good_file = SimpleEnv.env_file_name(TestNodeConfig.good_name)
        if os.path.exists(good_file):
            os.remove(good_file)





