import logging
import queue

logger = logging.getLogger(__name__)

class MarketQueue:
    """
        The MarketQueue buffers WantToCompute messages and passes them to the
        market algorithm on each tick, returning selected messages to reply to.
    """
    __instance = None

    def __new__(cls): # __new__ always a classmethod
        if not cls.__instance:
            cls.__instance = super(MarketQueue, cls).__new__(
                                cls)
        return cls.__instance

    def __init__(self):
        logger.debug('Creating new market queue')
        self.queue = queue.Queue()

    def push(self, msg):
        """ Adds offers to the end of the queue """
        logger.debug('Message pushed into the queue msg=%r', msg)
        self.queue.put(msg)
    
    def tick(self):
        """ Removes a single offer from the market queue
            WIP - Should be: 
            Calls the market algorithm and removes a set of messages from
            the queue when enough are collected or a timeout occurs
        """
        if not self.queue.empty():
            msg = self.queue.get()
            logger.debug('Ticked non empty queue, returning: msg=%r', msg)
            return msg        
        return None
