import json
import logging
from flask import Flask, request, send_file
from typing import Dict

from golem.client import Client
from .subscription import TaskStatus, Subscription, TaskType, InvalidTaskType, \
    InvalidTaskStatus, Task

logger: logging.Logger = logging.getLogger(__name__)
port: int = 55001
app: Flask = Flask(__name__)
golem_client: Client = None
subscriptions: Dict[str, Dict[TaskType, Subscription]] = dict()


def start(client: Client):
    global golem_client
    golem_client = client

    from twisted.internet.error import CannotListenError
    try:
        _start(port)
    except CannotListenError:
        _start(port+1)


# credit: https://gist.github.com/ianschenck/977379a91154fe264897
def _start(port: int):
    from twisted.internet import reactor
    from twisted.web.wsgi import WSGIResource
    from twisted.web.server import Site

    logger.info(f'Starting "Golem Unlimited Gateway" on port: {port}')
    reactor.listenTCP(
        port, Site(WSGIResource(reactor, reactor.getThreadPool(), app)))


def _json_response(msg: str, http_status_code: int = 200):
    return json.dumps({'msg': msg}), http_status_code


def _not_found(msg: str):
    return _json_response(f'{msg} not found', 404)


def _invalid_input(msg):
    return _json_response(f'invalid input: {msg}', 405)


@app.route('/')
def hello():
    """shows API doc generated from `swagger.yaml` spec"""
    return send_file('client-api-doc.html')


@app.errorhandler(404)
def page_not_found(error):
    return f'Not found. See <a href="/">API doc</a>', 404


@app.route('/settings')
def settings():
    return json.dumps(golem_client.get_settings())


@app.route('/subscriptions/<node_id>', methods=['GET'])
def all_subscriptions(node_id: str):
    """Gets subscription status"""

    if node_id not in subscriptions:
        return _not_found('subscription')

    return json.dumps(
        [s.to_json_dict() for s in subscriptions[node_id].values()])


@app.route('/subscriptions/<node_id>/<task_type>', methods=['PUT'])
def subscribe(node_id: str, task_type: str):
    """Creates or amends subscription to Golem Network"""

    status_code = 200
    if node_id not in subscriptions:
        subscriptions[node_id] = dict()

    try:
        task_type = TaskType.match(task_type)
    except InvalidTaskType as e:
        return _invalid_input(e)

    if task_type not in subscriptions[node_id]:
        subscription = Subscription(task_type)
        subscriptions[node_id][task_type] = subscription
        status_code = 201
    else:
        subscription = subscriptions[node_id][task_type]

    return subscription.to_json(), status_code


@app.route('/subscriptions/<node_id>/<task_type>', methods=['GET'])
def subscription(node_id: str, task_type: str):
    """Gets subscription status"""

    if node_id not in subscriptions:
        return _not_found('subscription')

    try:
        task_type = TaskType.match(task_type)
    except InvalidTaskType as e:
        return _invalid_input(e)

    if task_type not in subscriptions[node_id]:
        return _not_found('subscription')

    return subscriptions[node_id][task_type].to_json()


@app.route('/subscriptions/<node_id>/<task_type>', methods=['DELETE'])
def unsubscribe(node_id: str, task_type: str):
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


@app.route('/<node_id>/tasks/<uuid:task_id>', methods=['POST'])
def want_to_compute_task(node_id, task_id):
    """Sends task computation willingness"""

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


@app.route('/<node_id>/tasks/<task_id>', methods=['GET'])
def task_info(node_id: str, task_id: str):
    """Gets task information"""

    if node_id not in subscriptions:
        return _not_found('subscription')

    for s in subscriptions[node_id].values():
        if task_id in s.events:
            return json.dumps(s.events[task_id].task.to_json_dict())

    return _not_found('task')


@app.route('/<node_id>/subtasks/<uuid:subtask_id>', methods=['PUT'])
def confirm_subtask(node_id, subtask_id):
    """Confirms subtask computation start"""

    if node_id not in subscriptions:
        return _not_found('subscription')

    # TODO: get real task type
    subscriptions[node_id][TaskType.Blender].increment(TaskStatus.requested)

    return _json_response('OK')


@app.route('/<node_id>/subtasks/<uuid:subtask_id>', methods=['GET'])
def subtask_info(node_id, subtask_id):
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
def subtask_result(node_id, subtask_id):
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
def cancel_subtask(node_id, subtask_id):
    """Cancels subtask computation (upon failure or resignation)"""

    if node_id not in subscriptions:
        return _not_found('subscription')

    return _json_response('OK')


@app.route('/<node_id>/resources', methods=['POST'])
def upload_resource(node_id):
    """Receives a resource file from a caller"""
    if node_id not in subscriptions:
        return _not_found('subscription')

    for (filename, file) in request.files.items():
        # file.save(filename)
        print(f'file {file.filename} saved as {filename}')

    return _json_response(f'upload successful {request.form}, {request.files}')


@app.route('/<node_id>/resources/<uuid:resource_id>', methods=['GET'])
def download_resource(node_id, resource_id):
    """Sends a binary resource to a caller"""
    if node_id not in subscriptions:
        return _not_found('subscription')

    return send_file('foo')


@app.route('/<node_id>/<task_type>/events', methods=['GET'])
def fetch_events(node_id: str, task_type: str):
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
