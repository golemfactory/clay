import json
import logging
from flask import Flask, request, send_file
from pathlib import Path
from twisted.internet import reactor
from twisted.web.server import Site
from twisted.web.wsgi import WSGIResource
from typing import Dict
import wsgidav
from wsgidav.dav_error import DAVError, get_http_status_string
from wsgidav.wsgidav_app import WsgiDAVApp
from wsgidav.dir_browser import WsgiDavDirBrowser
from wsgidav.request_resolver import RequestResolver
from wsgidav.http_authenticator import HTTPAuthenticator

from golem.client import Client
from .subscription import SubtaskStatus, Subscription, TaskType, \
    InvalidTaskType, InvalidTaskStatus

logger: logging.Logger = logging.getLogger(__name__)
default_port: int = 55001
app: Flask = Flask(__name__)
golem_client: Client = None
# TODO: persist this in case of whole gateway failure
subscriptions: Dict[str, Dict[TaskType, Subscription]] = dict()


def start(client: Client) -> None:
    global golem_client
    golem_client = client

    from twisted.internet.error import CannotListenError
    try:
        _start(default_port)
    except CannotListenError:
        _start(default_port + 1)


# credit: https://gist.github.com/ianschenck/977379a91154fe264897
def _start(port: int) -> None:
    logger.info(f'Starting "Golem Unlimited Gateway" on port: {port}')
    reactor.listenTCP(
        port, Site(WSGIResource(reactor, reactor.getThreadPool(), app)))

    _start_web_dav(port + 10)


def _start_web_dav(port):
    global golem_client
    root_path = golem_client.task_manager.root_path
    config = {
        "port": port,
        "provider_mapping": {
            "/": root_path,
        },
        # TODO: dir browser is not secure
        'middleware_stack': [
            HTTPAuthenticator,
            WsgiDavDirBrowser,
            RequestResolver
        ],
        "dir_browser": {
            "enable": True,
        },
        "simple_dc": {
            "user_mapping": {
                "*": True
            }
        },
        # Verbose Output
        # 0 - no output
        # 1 - no output (excepting application exceptions)
        # 2 - show warnings
        # 3 - show single line request summaries (for HTTP logging)
        # 4 - show additional events
        # 5 - show full request/response header info (HTTP Logging)
        #     request body and GET response bodies not shown

        # Log Level Matrix
        # ~~~~~~~~~~~~~~~~
        #
        # +---------+--------+---------------------------------------------------------------+
        # | Verbose | Option |                       Log level                               |
        # | level   |        +-------------+------------------------+------------------------+
        # |         |        | base logger | module logger(default) | module logger(enabled) |
        # +=========+========+=============+========================+========================+
        # |    0    | -qqq   | CRITICAL    | CRITICAL               | CRITICAL               |
        # +---------+--------+-------------+------------------------+------------------------+
        # |    1    | -qq    | ERROR       | ERROR                  | ERROR                  |
        # +---------+--------+-------------+------------------------+------------------------+
        # |    2    | -q     | WARN        | WARN                   | WARN                   |
        # +---------+--------+-------------+------------------------+------------------------+
        # |    3    |        | INFO        | INFO                   | **DEBUG**              |
        # +---------+--------+-------------+------------------------+------------------------+
        # |    4    | -v     | DEBUG       | DEBUG                  | DEBUG                  |
        # +---------+--------+-------------+------------------------+------------------------+
        # |    5    | -vv    | DEBUG       | DEBUG                  | DEBUG                  |
        # +---------+--------+-------------+------------------------+------------------------+

        "verbose": 3,
    }

    logger.info(f'Starting "Golem Unlimited WebDav" on port: {port}')
    try:
        wsgidav._base_logger.propagate = True
        dav_app = WrappedWsgiDAVApp(WsgiDAVApp(config))
    except DAVError as err:
        import traceback
        logger.error("wsgiDav error: %r:\n%s", err, traceback.format_exc())
        raise err

    reactor.listenTCP(
        port, Site(WSGIResource(reactor, reactor.getThreadPool(), dav_app)))


class WrappedWsgiDAVApp:
    def __init__(self, inner_app):
        self.inner_app = inner_app

    def __call__(self, environ, start_response):
        try:
            for v in self.inner_app(environ, start_response):
                yield v
        except DAVError as e:
            start_response(get_http_status_string(e.value), [])
            yield b""

# from flask import after_this_request
# @app.before_request
# def before():
#     print(request.json)
#
#     @after_this_request
#     def after(response):
#         print(response)
#         return response
# def log_exception(e, **extra):
#     # add all necessary log info here
#     logger.info(f'dumping flask request: {request}, args: {request.args},'
#                 f'json: {request.json}')
#
# from flask import got_request_exception
# got_request_exception.connect(log_exception)


def _json_response(msg: str, http_status_code: int = 200) -> (str, int):
    return json.dumps({'msg': msg}), http_status_code


def _not_found(msg: str) -> (str, int):
    return _json_response(f'{msg} not found', 404)


def _invalid_input(msg) -> (str, int):
    return _json_response(f'invalid input: {msg}', 400)


@app.route('/')
def hello():
    """shows API doc generated from `swagger.yaml` spec"""
    return send_file('client-api-doc.html')


@app.errorhandler(404)
def page_not_found(_error) -> (str, int):
    return _json_response("Not found. See <a href='/'>API doc</a>", 404)


@app.errorhandler(400)
def bad_request(error) -> (str, int):
    return _json_response(str(error), 400)


@app.route('/settings')
def settings() -> str:
    return json.dumps(golem_client.get_settings())


@app.route('/subscriptions/<node_id>', methods=['GET'])
def all_subscriptions(node_id: str) -> (str, int):
    """Gets subscription status"""

    if node_id not in subscriptions:
        return _not_found(f'subscription for {node_id}')

    logger.debug('all subscriptions for %s', node_id)
    return json.dumps(
        [subs.to_json_dict() for subs in subscriptions[node_id].values()])


@app.route('/subscriptions/<node_id>/<task_type>', methods=['PUT'])
def subscribe(node_id: str, task_type: str) -> (str, int):
    """Creates or amends subscription to Golem Network"""

    try:
        subs = Subscription(
            node_id,
            task_type,
            request.json,
            golem_client.task_server.task_keeper.task_headers,
        )
    except InvalidTaskType as e:
        return _invalid_input(e)
    except AttributeError:
        return _invalid_input('request body is required')
    except KeyError as e:
        return _invalid_input(f'key {e} is missing in request body')
    except ValueError as e:
        return _invalid_input(str(e))

    if node_id not in subscriptions:
        subscriptions[node_id] = dict()

    status_code = 200
    if subs.task_type not in subscriptions[node_id]:
        status_code = 201

    subscriptions[node_id][subs.task_type] = subs

    logger.info('%s %s', status_code == 200 and 'updated' or 'created', subs)
    return json.dumps(subs.to_json_dict()), status_code


@app.route('/subscriptions/<node_id>/<task_type>', methods=['GET'])
def subscription(node_id: str, task_type: str) -> (str, int):
    """Gets subscription status"""

    try:
        subs = subscriptions[node_id][TaskType.match(task_type)]
    except InvalidTaskType as e:
        return _invalid_input(e)
    except KeyError:
        return _not_found(f'subscription for {node_id}/{task_type}')

    logger.debug('subscription info %s', subs)
    return json.dumps(subs.to_json_dict())


@app.route('/subscriptions/<node_id>/<task_type>', methods=['DELETE'])
def unsubscribe(node_id: str, task_type: str) -> (str, int):
    """Removes subscription"""

    try:
        subs = subscriptions[node_id].pop(TaskType.match(task_type))
    except InvalidTaskType as e:
        return _invalid_input(e)
    except KeyError:
        return _not_found(f'subscription for {node_id}/{task_type}')

    logger.info('removed %s', subs)
    return _json_response('subscription deleted')


@app.route('/<node_id>/tasks/<task_id>', methods=['POST'])
def want_to_compute_task(node_id, task_id) -> (str, int):
    """Sends task computation willingness"""

    if node_id not in subscriptions:
        return _not_found(f'subscription for {node_id}')

    for subs in subscriptions[node_id].values():
        if task_id in subs.events:
            try:
                subs.request_subtask(golem_client, task_id)
                logger.info('want task %s for %s', task_id, subs)
                return _json_response('OK')
            except KeyError as e:
                return _not_found(f'task {e}')
    else:
        return _not_found(f'task {task_id}')


@app.route('/<node_id>/tasks/<task_id>', methods=['GET'])
def task_info(node_id: str, task_id: str) -> (str, int):
    """Gets task information"""

    if node_id not in subscriptions:
        return _not_found(f'subscription for {node_id}')

    for subs in subscriptions[node_id].values():
        if task_id in subs.events:
            logger.debug('task info %s for %s', task_id, subs)
            return json.dumps(subs.events[task_id].task.to_json_dict())
    else:
        return _not_found(f'task {task_id}')


@app.route('/<node_id>/subtasks/<subtask_id>', methods=['PUT'])
def confirm_subtask(node_id, subtask_id) -> (str, int):
    """Confirms subtask computation start"""

    if node_id not in subscriptions:
        return _not_found(f'subscription for {node_id}')

    for subs in subscriptions[node_id].values():
        if subtask_id in subs.events:
            logger.info('started subtask %s for %s', subtask_id, subs)
            subs.increment(SubtaskStatus.started)
            return _json_response('OK')
    else:
        return _not_found(f'subtask {subtask_id}')


@app.route('/<node_id>/subtasks/<subtask_id>', methods=['GET'])
def subtask_info(node_id, subtask_id) -> (str, int):
    """Gets subtask information"""

    if node_id not in subscriptions:
        return _not_found(f'subscription for {node_id}')

    for subs in subscriptions[node_id].values():
        if subtask_id in subs.events:
            logger.debug('subtask info %s for %s', subtask_id, subs)
            return json.dumps(subs.events[subtask_id].subtask.to_json_dict())
    else:
        return _not_found(f'subtask {subtask_id}')


@app.route('/<node_id>/subtasks/<subtask_id>', methods=['POST'])
def subtask_result(node_id, subtask_id) -> (str, int):
    """Reports subtask computation result"""

    try:
        status = SubtaskStatus.match(request.json['status'])
    except KeyError as e:
        return _invalid_input('{e} is required in body')
    except InvalidTaskStatus as e:
        return _invalid_input(e)

    # TODO: SubtaskStatus.timedout is not send(?), but should be counted
    if status not in [SubtaskStatus.succeeded, SubtaskStatus.failed]:
        logger.warning('wrong %s result for subtask %s', status, subtask_id)
        return _invalid_input(f'subtask result status {status} '
                              f'must be one of: succeeded or failed')

    if node_id not in subscriptions:
        return _not_found(f'subscription for {node_id}')

    for subs in subscriptions[node_id].values():
        if subtask_id in subs.events:
            subtask = subs.events[subtask_id].subtask

            if status == SubtaskStatus.succeeded:
                if 'path' not in request.json:
                    return _invalid_input('path is required')

                root_path = Path(golem_client.task_manager.root_path)
                result = {"data": [
                    str(path) for path in
                    root_path.joinpath(request.json['path']).glob('*')
                ]}

                try:
                    golem_client.task_server.send_results(
                        subtask_id,
                        subtask.task_id,
                        result
                    )
                except RuntimeError as e:
                    return _json_response(str(e), 500)

                # TODO: should we call
                # golem_client.task_server.task_computer.__task_finished(subtask)

            else:  # status == SubtaskStatus.failed:
                if 'reason' not in request.json:
                    return _invalid_input('reason is required')

                golem_client.task_server.send_task_failed(
                    subtask_id,
                    subtask.task_id,
                    request.json['reason'],
                )

            subs.increment(status)
            logger.info('%s subtask %s for %s', status, subtask_id, subs)
            return _json_response('OK')
    else:
        return _not_found(f'subtask {subtask_id}')


@app.route('/<node_id>/subtasks/<subtask_id>/cancel', methods=['POST'])
def cancel_subtask(node_id, subtask_id) -> (str, int):
    """Cancels subtask computation (upon failure or resignation)"""

    if node_id not in subscriptions:
        return _not_found(f'subscription for {node_id}')

    for subs in subscriptions[node_id].values():
        if subtask_id in subs.events and subtask_id in \
                golem_client.task_server.task_sessions:
            session = golem_client.task_server.task_sessions[subtask_id]
            session.send_subtask_cancel(subtask_id)
            subs.increment(SubtaskStatus.cancelled)
            logger.info('cancelled subtask %s for %s', subtask_id, subs)
            return _json_response('OK')
    else:
        return _not_found(f'subtask {subtask_id}')


@app.route('/<node_id>/<task_type>/events', methods=['GET'])
def fetch_events(node_id: str, task_type: str) -> (str, int):
    """List events for given node id and task type; newer than last event id"""

    last_event_id = int(request.args.get('lastEventId', -1))

    try:
        subs = subscriptions[node_id][TaskType.match(task_type)]

        logger.debug('events for subscription %s', subs)
        return json.dumps([e.to_json_dict()
                           for e in subs.events_after(last_event_id)])
    except InvalidTaskType as e:
        return _invalid_input(e)
    except KeyError as e:
        return _not_found(f'subscription for {e}')
