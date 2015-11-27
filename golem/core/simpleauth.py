import uuid


# @see: http://zesty.ca/python/uuid.html
class SimpleAuth(object):
    """ Metaclass for simple id generation methods. """

    @classmethod
    def generate_uuid(cls):
        """ Return new UUID4 """
        return uuid.uuid4()
