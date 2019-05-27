import logging

logger = logging.getLogger("tools")

options = {
    0: 'kB',
    1: 'MB',
    2: 'GB'
}


def dir_size_to_display(dir_size):
    if dir_size // (1024 * 1024 * 1024) > 0:
        dir_size = round(float(dir_size) / (1024 * 1024 * 1024), 1)
        index = 2
    elif dir_size // (1024 * 1024) > 0:
        dir_size = round(float(dir_size) / (1024 * 1024), 1)
        index = 1
    else:
        dir_size = round(float(dir_size) / 1024, 1)
        index = 0
    return dir_size, index


def translate_resource_index(index):
    if index in options:
        return options[index]
    else:
        logger.error("Wrong memory unit index: {} ".format(index))
        return ''
