# Golem logging configuration file.
# If you want to modify it locally the preferred way to do this is to create
# loggingconfig_local.py and overwrite LOGGING dict. Typical use case is:
# from loggingconfig import LOGGING
# LOGGING['handlers']['console']['level'] = 'DEBUG'
# LOGGING['root']['level'] = 'DEBUG'
# or
# LOGGING['handlers']['console']['level'] = 'DEBUG'
# LOGGING['loggers']['golem.task.taskmanager'] = {
#     'level': 'DEBUG',
#     'propagate': False,
#     'handlers': ['console',],
# }

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,  # False is required for golem.tools.assertlogs
    'formatters': {
        'simple': {
            'format': '%(levelname)-8s [%(name)-35s] %(message)s',
        },
        'date': {
            'format': '%(asctime)s %(levelname)-8s %(name)-35s %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'filters': {},
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'WARNING',
            'formatter': 'simple',
            'filters': [],
            'stream': 'ext://sys.stderr',
        },
        'file': {
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'level': 'INFO',
            'formatter': 'date',
            'filename': '%(datadir)slogs/golem%(suffix)s.log',  # suffix is substituted in golem.core.common.config_logging()
            'when': 'D',
            'interval': 1,
            'backupCount': 5,
            'encoding': 'utf-8',
        },
    },
    'root': {
        'level': 'WARNING',
        'handlers': ['console', 'file', ],
        'filters': [],
    },
    'loggers': {
        'golem': {
            'level': 'DEBUG',
            'propagate': True,
        },
        'apps': {
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
