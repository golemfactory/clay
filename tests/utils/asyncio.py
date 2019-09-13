import asyncio
from mock import MagicMock

from twisted.trial.unittest import TestCase as TwistedTestCase

from golem.core.common import install_reactor
from golem.tools.testwithreactor import uninstall_reactor


class AsyncMock(MagicMock):
    """
    Extended MagicMock to keep async calls async
    """
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)


class TwistedAsyncioTestCase(TwistedTestCase):
    """
    A wrapper for TwistedTestCase to ensure it works with asyncio
    Replace with @pytest.mark.asyncio when removing twisted from these tests
    """
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
