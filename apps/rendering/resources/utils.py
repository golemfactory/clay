import cv2
import logging
from contextlib import contextmanager
from typing import Optional

from apps.rendering.resources.imgrepr import OpenCVError


@contextmanager
def handle_opencv_image_error(logger: Optional[logging.Logger] = None):
    """
    This context manager will catch exceptions that might be thrown by OpenCV
    and write them to log.

    The Result is to get outside the managed context if operation was
    successful.

    with handle_image_error() as handler_result:
        do_stuff_with_images()

    if handler_result.success:
        print("do_stuff_with_images() went successfully")
    else:
        print("do_stuff_with_images() raised excetpion")


    This can also be used as a function decorator:

    @handle_image_error()
    def do_other_stuff_with_images():
        [...]
    """
    if logger is None:
        logger = logging.getLogger("apps.rendering")

    class Result:
        def __init__(self):
            self.success = False

    try:
        result = Result()
        yield result
        result.success = True
    except (cv2.error, OpenCVError, FileNotFoundError):
        logger.exception("Failed to operate on image with OpenCV")


@contextmanager
def handle_none(opt_context, raise_if_none: Optional[Exception] = None):
    """
    The purpose of this context manager is to handle such situation:

    with create_context_manager() as context_manager:
        do_stuff(context_manager)

    If create_context_manager() returns None, the code will fail, because
    NoneType has no __enter__ method.


    With this wrapper you can do this:

    with handle_none(create_context_manager()) as context_manager:
        do_stuff(context_manager)

    Now if create_context_manager() returns None, then context_manager will be
    also None.


    Optionally you can define raise_if_none, which will raise the provided
    exception, instead of running do_stuff.
    """

    if opt_context is not None:
        with opt_context:
            yield opt_context
    else:
        if raise_if_none is not None:
            # pylint thinks we're raising None here
            raise raise_if_none  # pylint: disable=raising-bad-type
        yield None
