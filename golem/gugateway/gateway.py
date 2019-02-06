import json
import logging
from flask import Flask, request, send_file
from twisted.internet import reactor
from twisted.web.server import Site
from twisted.web.wsgi import WSGIResource
from typing import Dict
from wsgidav.wsgidav_app import WsgiDAVApp
from wsgidav.dir_browser import WsgiDavDirBrowser

from golem.client import Client
from .subscription import TaskStatus, Subscription, TaskType, InvalidTaskType, \
    InvalidTaskStatus, Task

logger: logging.Logger = logging.getLogger(__name__)
port: int = 55001
app: Flask = Flask(__name__)
golem_client: Client = None
subscriptions: Dict[str, Dict[TaskType, Subscription]] = dict()


def start(client: Client) -> None:
    global golem_client
    golem_client = client

    from twisted.internet.error import CannotListenError
    try:
        _start(port)
    except CannotListenError:
        _start(port + 1)


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
        'middleware_stack': [WsgiDavDirBrowser],
        "dir_browser": {
            "enable": True,
        },
        # Verbose Output
        # 0 - no output
        # 1 - no output (excepting application exceptions)
        # 2 - show warnings
        # 3 - show single line request summaries (for HTTP logging)
        # 4 - show additional events
        # 5 - show full request/response header info (HTTP Logging)
        #     request body and GET response bodies not shown
        "verbose": 3,
    }

    logger.info(f'Starting "Golem Unlimited WebDav" on port: {port}')
    try:
        import wsgidav
        wsgidav._base_logger.propagate = True
        dav_app = WsgiDAVApp(config)
    except Exception as err:
        import traceback
        logger.error("wsgiDav error: %r:\n%s", err, traceback.format_exc())
        raise err
    reactor.listenTCP(
        port, Site(WSGIResource(reactor, reactor.getThreadPool(), dav_app)))


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
        return _not_found('subscription')

    return json.dumps(
        [s.to_json_dict() for s in subscriptions[node_id].values()])


@app.route('/subscriptions/<node_id>/<task_type>', methods=['PUT'])
def subscribe(node_id: str, task_type: str) -> (str, int):
    """Creates or amends subscription to Golem Network"""

    status_code = 200
    if node_id not in subscriptions:
        subscriptions[node_id] = dict()

    try:
        task_type = TaskType.match(task_type)
    except InvalidTaskType as e:
        return _invalid_input(e)

    if task_type not in subscriptions[node_id]:
        status_code = 201

    if request.json is None:
        return _invalid_input('request body is required')

    try:
        subscription = Subscription(task_type, request.json)
    except AttributeError as e:
        return _invalid_input('request body is required')
    except KeyError as e:
        return _invalid_input(f'key {e} is missing in request body')
    except ValueError as e:
        return _invalid_input(str(e))

    subscriptions[node_id][task_type] = subscription

    return json.dumps(subscription.to_json_dict()), status_code


@app.route('/subscriptions/<node_id>/<task_type>', methods=['GET'])
def subscription(node_id: str, task_type: str) -> (str, int):
    """Gets subscription status"""

    if node_id not in subscriptions:
        return _not_found('subscription')

    try:
        task_type = TaskType.match(task_type)
    except InvalidTaskType as e:
        return _invalid_input(e)

    if task_type not in subscriptions[node_id]:
        return _not_found('subscription')

    return json.dumps(subscriptions[node_id][task_type].to_json_dict())


@app.route('/subscriptions/<node_id>/<task_type>', methods=['DELETE'])
def unsubscribe(node_id: str, task_type: str) -> (str, int):
    """Removes subscription"""

    if node_id not in subscriptions:
        return _not_found('subscription')

    try:
        task_type = TaskType.match(task_type)
    except InvalidTaskType as e:
        return _invalid_input(e)

    if task_type not in subscriptions[node_id]:
        return _not_found('subscription')

    subscriptions.pop(node_id)
    return _json_response('subscription deleted')


@app.route('/<node_id>/tasks/<task_id>', methods=['POST'])
def want_to_compute_task(node_id, task_id) -> (str, int):
    """Sends task computation willingness"""

    if node_id not in subscriptions:
        return _not_found('subscription')

    for s in subscriptions[node_id].values():
        if task_id in s.events:
            subscription = s
            break
    else:
        return _not_found(f'task {task_id}')

    try:
        subscription.request_task(golem_client, task_id)
    except KeyError as e:
        return _not_found(f'task {e}')

    return _json_response('OK')


@app.route('/<node_id>/tasks/<task_id>', methods=['GET'])
def task_info(node_id: str, task_id: str) -> (str, int):
    """Gets task information"""

    try:
        task = Task(golem_client.get_known_tasks()[task_id])
        return json.dumps(task.to_json_dict())
    except KeyError as e:
        return _not_found(f'task {e}')


@app.route('/<node_id>/subtasks/<uuid:subtask_id>', methods=['PUT'])
def confirm_subtask(node_id, subtask_id) -> (str, int):
    """Confirms subtask computation start"""

    if node_id not in subscriptions:
        return _not_found('subscription')

    # TODO: get real task type
    subscriptions[node_id][TaskType.Blender].increment(TaskStatus.requested)

    return _json_response('OK')


@app.route('/<node_id>/subtasks/<uuid:subtask_id>', methods=['GET'])
def subtask_info(node_id, subtask_id) -> (str, int):
    """Gets subtask information"""

    if node_id not in subscriptions:
        return _not_found('subscription')

    return json.dumps({
        'subtaskId': '435bd45a-12d4-144f-233c-6e845eabffe0',
        'description': 'some desc',
        'resource': {
            'resourceId': '87da97cd-234s-bc32-3d42-6e845eabffe0',
            'metadata': '{"size": 123}'
        },
        'deadline': 1542903681123,
        'price': 3,
        'extraData': '{"foo": "bar"}'
    })


@app.route('/<node_id>/subtasks/<uuid:subtask_id>', methods=['POST'])
def subtask_result(node_id, subtask_id) -> (str, int):
    """Reports subtask computation result"""

    if node_id not in subscriptions:
        return _not_found('subscription')

    if 'status' not in request.json:
        return _invalid_input('status required')

    try:
        # TODO: get real task type
        subscriptions[node_id][TaskType.Blender].increment(
            request.json['status'])
    except InvalidTaskStatus as e:
        return _invalid_input(e)

    return _json_response('OK')


@app.route('/<node_id>/subtask/<uuid:subtask_id>/cancel', methods=['POST'])
def cancel_subtask(node_id, subtask_id) -> (str, int):
    """Cancels subtask computation (upon failure or resignation)"""

    if node_id not in subscriptions:
        return _not_found('subscription')

    return _json_response('OK')


@app.route('/<node_id>/<task_type>/events', methods=['GET'])
def fetch_events(node_id: str, task_type: str) -> (str, int):
    """List events for given node id and task type; newer than last event id"""

    if node_id not in subscriptions:
        return _not_found('subscription')

    try:
        task_type = TaskType.match(task_type)
    except InvalidTaskType as e:
        return _invalid_input(e)

    if task_type not in subscriptions[node_id]:
        return _not_found('subscription')

    subscription = subscriptions[node_id][task_type]

    for task_id, header in golem_client.get_known_tasks().items():
        if header['environment'].lower() != task_type.name.lower():
            continue

        subscription.add_task_event(task_id, header)

    last_event_id = int(request.args.get('lastEventId', -1))
    try:
        return json.dumps([e.to_json_dict()
                           for e in subscription.events_after(last_event_id)])
    except KeyError as e:
        return _invalid_input(e)
