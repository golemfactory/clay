from flask import Flask, request, send_file
import json

app = Flask(__name__)

subscriptions = dict()


@app.route('/')
def hello():
    """shows API doc generated from `swagger.yaml` spec"""
    return send_file('openapi/client-api-doc.html')


@app.errorhandler(404)
def page_not_found(error):
    return f'Not found. See <a href="/">API doc</a>', 404


@app.route('/subscribe/<node_id>', methods=['PUT'])
def subscribe(node_id):
    """Creates or amends subscription to Golem Network"""
    if 'taskType' not in request.json:
        return f'no task type'

    task_type = request.json['taskType']
    if node_id not in subscriptions:
        subscriptions[node_id] = set()

    if task_type in subscriptions[node_id]:
        subscriptions[node_id].remove(task_type)

        return f'node id: {node_id} already subscribed for {task_type} tasks. ' \
               f'Removing. Current subscription is {subscriptions[node_id]}'

    subscriptions[node_id].add(task_type)

    return f'node id: {node_id} subscribed for {task_type} tasks. ' \
           f'Current subscription is {subscriptions[node_id]}'


@app.route('/subscribe/<node_id>', methods=['GET'])
def subscriber(node_id):
    """Gets subscription status"""

    if node_id not in subscriptions:
        return 'Subscription not found', 404

    return json.dumps({
        'active': True,
        'tasksTypes': list(subscriptions[node_id]),
        'tasksStats': {
            'requested': 7,
            'succeded': 5,
            'failed': 1,
            'timedout': 1
        }
    })


@app.route('/subscribe/<node_id>', methods=['DELETE'])
def usubscribe(node_id):
    """Deletes subscription"""

    if node_id not in subscriptions:
        return 'Subscription not found', 404

    subscriptions.pop(node_id)

    return 'subscription deleted'


@app.route('/<node_id>/resource/<resource_id>', methods=['GET'])
def download_resource(node_id, resource_id):
    """Downloads binary resource"""
    if node_id not in subscriptions:
        return 'Subscription not found', 404

    return send_file('foo')


@app.route('/<node_id>/uploadResource', methods=['POST'])
def upload_resource(node_id):
    """Uploads an resource file"""
    if node_id not in subscriptions:
        return 'Subscription not found', 404

    for (filename, file) in request.files.items():
        # file.save(filename)
        print(f'file {file.filename} saved as {filename}')

    return f'upload successful {request.form}, {request.files}'


@app.route('/<node_id>/events', methods=['GET'])
def fetch_events(node_id):
    """List events for given node id; starting after last event id"""

    if node_id not in subscriptions:
        return 'Subscription not found', 404

    # TODO: interpret body.event_id

    return json.dumps([{
        'eventId': 1,
        'task': None,
        'resource': {
            'resource_id': '1234',
            'metadata':
                '{"size": 120, "filename": "foo.json", "atime": 1542903681123}'
        },
        'verificationResult': None
    }, {
        'eventId': 2,
        'task': {
            'taskId': '682e9b26-ed89-11e8-a9e0-6e845eabffe0',
            'perfIndex': 314,
            'maxResourceSize': 110,
            'maxMemorySize': 10,
            'numCores': 2,
            'price': 12,
            'extraData': '{"foo": "bar"}'
        },
        'resource': None,
        'verificationResult': None
    }])


@app.route('/<node_id>/task/<task_id>', methods=['POST', 'GET', 'DELETE'])
def task(node_id, task_id):
    """Sends task computation willingness"""

    if node_id not in subscriptions:
        return 'Subscription not found', 404

    if request.method == 'POST':
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
    elif request.method == 'GET':
        return json.dumps({
            'taskId': '682e9b26-ed89-11e8-a9e0-6e845eabffe0',
            'perfIndex': 314,
            'maxResourceSize': 110,
            'maxMemorySize': 10,
            'numCores': 2,
            'price': 12,
            'extraData': '{"foo": "bar"}'
        })
    else:  # DELETE
        return 'task deleted'
