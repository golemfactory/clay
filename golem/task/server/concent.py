import logging
import queue

from golem.network.concent.handlers_library import library


logger = logging.getLogger(__name__)

def process_messages_received_from_concent(concent_service):
    # Process first 50 messages only in one sync
    for _ in range(50):
        try:
            msg = concent_service.received_messages.get_nowait()
        except queue.Empty:
            break

        try:
            library.interpret(msg)
        except Exception:  # pylint: disable=broad-except
            logger.exception('Problem interpreting: %r', msg)

        concent_service.received_messages.task_done()
