import os

TEST_RES_DIRECTORY = "testing_task_resources"

class GNREnv:

    @classmethod
    def getTestTaskDirectory( cls ):
        return TEST_RES_DIRECTORY