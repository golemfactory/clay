class MarketQueue:
    class __MarketQueue:
        def __init__():
            self.queue = queue.Queue()

    instance = None

    def __new__(cls): # __new__ always a classmethod
        if not MarketQueue.instance:
            MarketQueue.instance = MarketQueue.__MarketQueue()

    @classmethod
    def push(cls, msg):
        instance.queue.put(msg)
    
    @classmethod
    def tick(cls):
        if not instance.queue.empty():
            return instance.queue.get()        
        return None
