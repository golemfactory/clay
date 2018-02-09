class ConcentException(Exception):
    """
    General exception for all Concent related errors
    """
    pass


class ConcentRequestException(ConcentException):
    """
    Concent request was ill-formed
    """
    pass


class ConcentServiceException(ConcentException):
    """
    Concent service error
    """
    pass


class ConcentUnavailableException(ConcentException):
    """
    Concent is not available
    """
    pass


class ConcentVerificationFailed(ConcentException):
    pass
