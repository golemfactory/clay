

def calculate_subtask_payment(
        price_per_hour: int, computation_time: int) -> int:
    """
    calculates the GNT wei amount to be paid for `computation_time` of
    resource usage with a given price of an hour of computation time,
    rounded up

    :param price_per_hour: [ GNT wei / hour ]
    :param computation_time: [ seconds ]
    :return: [ GNT wei ]
    """
    # price_per_hour is
    # computation_time is expressed in seconds
    """
    This is equivalent to: math.ceil(price_per_hour * computation_time // 3600)
    
    Don't use math.ceil (this is general advice, not specific to the case here)
    >>> math.ceil(10 ** 18 / 6)
    166666666666666656
    >>> (10 ** 18 + 5) // 6
    166666666666666667
    """
    return (price_per_hour * computation_time + 3599) // 3600


def calculate_max_usage(budget: int, price_per_hour: int) -> int:
    """
    calculate the usage expressed in seconds of computation time that
    can be allocated for a computation with a given budget and hourly rate,
    rounded up

    :param budget: [ GNT wei ]
    :param price_per_hour: [ GNT wei / hour ]
    :return: [ seconds ]
    """
    """
    This is equivalent to: math.ceil(budget * 3600 // price_per_hour)

    Don't use math.ceil (this is general advice, not specific to the case here)
    >>> math.ceil(10 ** 18 / 6)
    166666666666666656
    >>> (10 ** 18 + 5) // 6
    166666666666666667
    """

    return (budget * 3600 + price_per_hour - 1) // price_per_hour
