class ConcentError(Exception):
    """
    General exception for all Concent related errors
    """
    pass


class ConcentRequestError(ConcentError):
    """
    Concent request was ill-formed
    """
    pass


class ConcentServiceError(ConcentError):
    """
    Concent service error
    """
    pass


class ConcentUnavailableError(ConcentError):
    """
    Concent is not available
    """
    pass


class ConcentVersionMismatchError(ConcentError):
    def __init__(self, *args, **kwargs):
        self.ours = kwargs.pop('ours', '<unknown>')
        self.theirs = kwargs.pop('theirs', '<unknown>')
        super().__init__(*args)

    def __str__(self):
        return "{parent} [{ours} (ours) != {theirs} (theirs)]".format(
            parent=super().__str__(),
            ours=self.ours,
            theirs=self.theirs,
        )
