from flask import Flask, request
import json
app = Flask(__name__)

@app.route('/')
def hello():
    return 'This is Golem Unlimited Gateway mock!'

@app.route('/subscribe/<node_id>')
def subscribe(node_id):
    return f'node id: {node_id} subscribed successfully'


@app.route('/<node_id>/fetchEvents')
def fetch_events(node_id):
    return json.dumps([
        {'task_id': 'some_id'},
        {'resource_id': 'rsc_id'},
        {'result_verification': 'res_id'}
    ])

@app.route('/<node_id>/eventsAck', methods=['POST'])
def events_ack(node_id):
    print(f'node {node_id} acks events %r' % request.json)
    return 'OK'

@app.route('/<node_id>/wantToCompute', methods=['POST'])
def want_to_compute(node_id):
    if request.json.get('task_id', None) == None:
        return "no task id given"

    print(f'node {node_id} wants to compute task %r' % request.json['task_id'])
    return json.dumps({
        'node_name': node_id,
        'task_id': request.json['task_id'],
        'perf_index': 123,
        'max_resource_size': 123124323,
        'max_memory_size': 2131232,
        'num_cores': 4,
        'price': 153,
        'concent_enabled': False,
        'extra_data': {'sth': 'oth'},
        'provider_public_key': 'a key',
        'provider_ethereum_public_key': 'a eth key',
    })

@app.route('/<node_id>/startResourcesPull/<resource_id>')
def start_resource_pull(node_id, resource_id):
    return 'OK'

# @app.route('/<node_id>/TaskResult/<task_id>')
# def task_result(node_id, task_id):
