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
    # False is required for golem.tools.assertlogs
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(levelname)-8s [%(name)-35s] %(message)s',
        },
        'date': {
            'format': '%(asctime)s %(levelname)-8s %(name)-35s %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'filters': {
        'sentry-metrics': {
            '()': 'golem.tools.customloggers.SentryMetricsFilter'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'simple',
            'filters': [],
            'stream': 'ext://sys.stderr',
        },
        'file': {
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'level': 'INFO',
            'formatter': 'date',
            # suffix is substituted in golem.core.common.config_logging()
            'filename': '%(logdir)s/golem%(suffix)s.log',
            'when': 'D',
            'interval': 1,
            'backupCount': 5,
            'encoding': 'utf-8',
        },
        'error-file': {
            'class': 'logging.FileHandler',
            'level': 'WARNING',
            'formatter': 'date',
            # suffix is substituted in golem.core.common.config_logging()
            'filename': '%(logdir)s/golem%(suffix)s.error.log',
            'encoding': 'utf-8',
        },
        'sentry': {
            'level': 'ERROR',
            'class': 'golem.tools.customloggers.SwitchedSentryHandler',
            'dsn': 'https://cdf4218c9dd24aa6adeb76ad0c990c9b:e6922bfaff9f49ccaa22ae4e406354aa@talkback.golem.network/2'  # noqa pylint: disable=line-too-long
        },
        'sentry-metrics': {
            'level': 'DEBUG',
            'class': 'golem.tools.customloggers.SwitchedSentryHandler',
            'filters': ['sentry-metrics'],
            'dsn': 'https://d0e50b89f1ef4794a4b7f82b06fbe1e7:1043fecec0db4b818ccf76eb03003d03@talkback.golem.network/5'  # noqa pylint: disable=line-too-long
        },
    },
    'root': {
        'level': 'WARNING',
        'handlers': ['console', 'file', 'error-file', 'sentry', 'sentry-metrics'],  # noqa pylint: disable=line-too-long
        'filters': [],
    },
    'loggers': {
        'golemapp': {
            'level': 'INFO',
            'propagate': True,
        },
        'golem': {
            'level': 'INFO',
            'propagate': True,
        },
        'golem.rpc.crossbar': {
            'level': 'INFO',
            'propagate': True,
        },
        'golem_sci': {
            'level': 'INFO',
            'propagate': True,
        },
        'twisted': {
            'level': 'WARNING',
            'propagate': True,
        },
        'golem.network': {'propagate': True},
        'golem.network.transport': {'propagate': True},
        'apps': {
            'level': 'DEBUG',
            'propagate': True,
        },
        'test': {
            'level': 'DEBUG',
            'propagate': False,
            'handlers': ['console', 'file', ],
        },
        'docker': {
            'level': 'INFO',
            'propagate': True,
        },
        'urllib3': {
            'level': 'INFO',
            'propagate': True,
        },
    },
}
