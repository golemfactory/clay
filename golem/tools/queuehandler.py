from logging import Handler


class QueueHandler(Handler):
    def __init__(self, queue):
        super(QueueHandler, self).__init__()
        self.queue = queue

    def emit(self, record):
        try:
            exc_info = record.exc_info
            if exc_info:
                record.exc_info = None
            self.queue.put_nowait(record)
        except Exception:
            self.handleError(record)
