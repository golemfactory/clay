import logging

logger = logging.getLogger("gui")

options = {
    0: 'kB',
    1: 'MB',
    2: 'GB'
}


def dir_size_to_display(dir_size):
    if dir_size / (1024 * 1024 * 1024) > 0:
        dir_size = round(float(dir_size) / (1024 * 1024 * 1024), 1)
        index = 2
    elif dir_size / (1024 * 1024) > 0:
        dir_size = round(float(dir_size) / (1024 * 1024), 1)
        index = 1
    else:
        dir_size = round(float(dir_size) / 1024, 1)
        index = 0
    return dir_size, index


def resource_size_to_display(max_resource_size):
    if max_resource_size / (1024 * 1024) > 0:
        max_resource_size /= (1024 * 1024)
        index = 2
    elif max_resource_size / 1024 > 0:
        max_resource_size /= 1024
        index = 1
    else:
        index = 0
    return max_resource_size, index


def translate_resource_index(index):
    if index in options:
        return options[ index ]
    else:
        logger.error("Wrong memory unit index: {} ".format(index))
        return ''