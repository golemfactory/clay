from .builders import builders
from .schedulers import schedulers
from .services import services
from .settings import buildbot_host
from .workers import workers
from .www import www


BuildmasterConfig = {
    'workers': workers,
    'protocols': {'pb': {'port': 9989}},
    'change_source': [],
    'schedulers': schedulers,
    'builders': builders,
    'services': services,
    'title': 'Golem',
    'titleURL': 'https://github.com/golemfactory/golem',
    'buildbotURL': buildbot_host + '/buildbot/',
    'www': www,
    'db': {
        'db_url' : 'sqlite:///state.sqlite',
    },
}
