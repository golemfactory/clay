import asyncio

from twisted.trial.unittest import TestCase as TwistedTestCase

from golem.core.common import install_reactor
from golem.tools.testwithreactor import uninstall_reactor


class TwistedAsyncioTestCase(TwistedTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            uninstall_reactor()  # Because other tests don't clean up
        except AttributeError:
            pass
        cls.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.loop)
        install_reactor()

    @classmethod
    def cleanUpClass(cls):  # cleanUp is also ran on errors in setUp's
        uninstall_reactor()
        cls.loop = None
        asyncio.set_event_loop(cls.loop)
