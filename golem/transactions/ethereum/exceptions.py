class NotEnoughFunds(Exception):
    def __init__(self, required=None, available=None, extension="GNT"):
        super().__init__()
        self.required = required
        self.available = available
        self.extension = extension

    def __str__(self):
        return "Not enough %s available. Required: %d, available: %d" % \
               (self.extension, self.required, self.available)
