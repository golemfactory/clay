import uuid

#@see: http://zesty.ca/python/uuid.html
class SimpleAuth:

    @classmethod
    def generateUUID( cls ):
        return uuid.uuid4()
