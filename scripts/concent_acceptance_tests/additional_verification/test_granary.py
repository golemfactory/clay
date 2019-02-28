from golem_messages.message import concents as concent_msg

from .base import SubtaskResultsVerifyBaseTest


import unittest
import inspect

def logPoint(context):
    'utility function used for module functions and class methods'
    callingFunction = inspect.stack()[1][3]
    print('in %s - %s()'.format(context, callingFunction))

def setUpModule():
    'called once, before anything else in this module'
    logPoint('module %s'.format(__name__))

def tearDownModule():
    'called once, after everything else in this module'
    logPoint('module %s'.format(__name__))

class SubtaskResultsVerifyTest(SubtaskResultsVerifyBaseTest):

    def test_granary(self):
        self.logPoint()
        print("WORKING")

    @classmethod
    def setUpClass(cls):
        'called once, before any tests'
        logPoint('class %s' % cls.__name__)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        'called once, after all tests, if setUpClass successful'
        logPoint('class %s' % cls.__name__)
        super().tearDownClass()

    def logPoint(self):
        'utility method to trace control flow'
        callingFunction = inspect.stack()[1][3]
        currentTest = self.id().split('.')[-1]
        print('in %s - %s()'.format(currentTest, callingFunction))
