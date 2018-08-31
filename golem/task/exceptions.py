class KwargsError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self.kwargs = kwargs

    def __str__(self):
        return "{parent} {kwargs}".format(
            parent=super().__str__(),
            kwargs=self.kwargs,
        )


class TaskError(KwargsError):
    pass


class TaskHeaderError(TaskError):
    pass
