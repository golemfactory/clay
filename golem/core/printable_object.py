


class PrintableObject:
    """
    a simple mixin that provides a default implementation of the `__str__`
    method that serializes the objects `__dict__` to the string for easier
    human-readable represenation of simple, dictionary-like objects
    """

    def __str__(self):
        return '%s <%s>' % (
            self.__class__.__name__,
            ', '.join(['%s: %s' % (k, v) for k, v in self.__dict__.items()])
        )
