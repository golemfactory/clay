import inspect
import logging

from autobahn.wamp import message


logger = logging.getLogger(__name__)


class WAMPBroker(object):
    def __init__(self, router, options=None):
        self.router = router
        self.options = options

    def processPublish(self, session, msg):
        logger.debug(inspect.currentframe().f_code.co_name)

    def processSubscribe(self, session, msg):
        logger.debug(inspect.currentframe().f_code.co_name)

    def processUnubscribe(self, session, msg):
        logger.debug(inspect.currentframe().f_code.co_name)


class WAMPMethod(object):
    def __init__(self):
        super(WAMPMethod, self).__init__()



class WAMPDealer(object):
    def __init__(self, router, options=None):
        self.router = router
        self.options = options
        self.registered_methods = {}

    def processRegister(self, session, msg):
        logger.debug(inspect.currentframe().f_code.co_name)

    def processUnregister(self, session, msg):
        logger.debug(inspect.currentframe().f_code.co_name)

    def processCall(self, session, msg):
        logger.debug(inspect.currentframe().f_code.co_name)

    def processCancel(self, session, msg):
        logger.debug(inspect.currentframe().f_code.co_name)

    def processYield(self, session, msg):
        logger.debug(inspect.currentframe().f_code.co_name)

    def processInvocationError(self, session, msg):
        logger.debug(inspect.currentframe().f_code.co_name)


class WAMPRouter(object):
    def __init__(self, realm, options=None):
        self.realm = realm

        self._options = options
        self._sessions = 0

        self._broker = WAMPBroker(self, self._options)
        self._dealer = WAMPDealer(self, self._options)

    def add_session(self, session):
        self._sessions += 1

        self._broker.add_session(session)
        self._dealer.add_session(session)

    def remove_session(self, session):
        self._sessions -= 1

        self._broker.remove_session(session)
        self._dealer.remove_session(session)

    def authorize(self, session, uri, action):
        logger.debug("WAMPRouter: authorize: {} {} {}".format(session, uri, action))
        return True

    def validate(self, payload_type, uri, args, kwargs):
        logger.debug("WAMPRouter: validate: {} {} {} {}".format(payload_type, uri, args, kwargs))
        return True

    def route(self, session, msg):
        logger.debug("WAMPRouter: route: {}".format(msg))

        if isinstance(msg, message.Call):
            self._dealer.processCall(session, msg)
        elif isinstance(msg, message.Register):
            self._dealer.processRegister(session, msg)
        elif isinstance(msg, message.Unregister):
            self._dealer.processUnregister(session, msg)

        # if isinstance(msg, message.Publish):
        #     self._broker.processPublish(session, msg)
        # elif isinstance(msg, message.Subscribe):
        #     self._broker.processSubscribe(session, msg)
        # elif isinstance(msg, message.Unsubscribe):
        #     self._broker.processUnsubscribe(session, msg)
        # elif isinstance(msg, message.Call):
        #     self._dealer.processCall(session, msg)
        # elif isinstance(msg, message.Register):
        #     self._dealer.processRegister(session, msg)
        # elif isinstance(msg, message.Unregister):
        #     self._dealer.processUnregister(session, msg)
        # elif isinstance(msg, message.Cancel):
        #     self._dealer.processCancel(session, msg)
        # elif isinstance(msg, message.Yield):
        #     self._dealer.processYield(session, msg)
        # elif isinstance(msg, message.Error) and msg.request_type == message.Invocation.MESSAGE_TYPE:
        #     self._dealer.processInvocationError(session, msg)

        else:
            raise Exception("WAMPRouter: unexpected message {}".format(msg.__class__))
