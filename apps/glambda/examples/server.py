import json
from flask import Flask
from flask import request
from flask import make_response
from flask import jsonify

app = Flask(__name__)

items = []

def get_next_id():
    ret_id = 0;
    for item in items:
        if item['id'] > ret_id:
            ret_id = item['id']
    return ret_id

def create_new_obj():
    return {
        'access_token': 'dummy_token',
        'id': get_next_id()
    }

MAGIC_TOKEN = 'Bearer qW8z15Ei3WU0IZhlwciGIEEPzZgTYA4egsfJP6mcCPA='

@app.route('/test', methods=['GET', 'POST'])
def hello():
    if request.headers.get('Authorization') != MAGIC_TOKEN:
        obj = {
            'error': 'invalid token'
        } 
        return make_response(jsonify(obj), 401)

    if request.method == 'GET':
        return make_response(jsonify(items))

    elif request.method == 'POST':
        obj = create_new_obj()

        items.append(obj)

        resp = make_response(jsonify(obj))
        resp.headers['Location'] = request.url_rule.rule + '/' + obj['id']

        return resp


@app.route('/test/<id>', methods=['GET'])
def hello_name(name):
    return "id {}!".format(id)

if __name__ == '__main__':
    app.run()
