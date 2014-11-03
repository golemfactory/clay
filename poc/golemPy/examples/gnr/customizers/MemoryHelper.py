import logging

logger = logging.getLogger(__name__)

options = {
    0: 'kB',
    1: 'MB',
    2: 'GB'
}

def resourceSizeToDisplay( maxResourceSize ):
    if maxResourceSize / ( 1024 * 1024 ) > 0:
        maxResourceSize /= ( 1024 * 1024 )
        index = 2
    elif maxResourceSize / 1024 > 0:
        maxResourceSize /= 1024
        index = 1
    else:
        index = 0
    return maxResourceSize, index

def translateResourceIndex( index ):
    if index in options:
        return options[ index ]
    else:
        logger.error("Wrong memory unit index: {} ".format( index ) )
        return ''