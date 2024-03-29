# coding=utf-8

import json
from os.path import join
from functools import wraps

from flask import Blueprint, request, abort, jsonify, render_template

from guniflask.utils.template import template_folder

from spiderhub import settings, jwt_manager, roles_required

static_folder = join(template_folder, 'static')

hello_world = Blueprint('hello_world', __name__, url_prefix='/hello-world',
                        template_folder=join(template_folder, 'hello_world'),
                        static_folder=static_folder,
                        static_url_path='/static')


def debug_only(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if settings['debug']:
            return func(*args, **kwargs)
        return render_template('debug_only.html'), 403

    return wrapper


@hello_world.route('/', methods=['GET'])
def home_page():
    return render_template('index.html')


accounts = {
    'root': {
        'password': '123456',
        'authorities': ['role_admin', 'role_user']
    }
}


@hello_world.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    data = request.get_json()
    if data is not None:
        username = data.get('username')
        password = data.get('password')
        if username in accounts and password == accounts[username]['password']:
            token = jwt_manager.create_access_token(accounts[username]['authorities'],
                                                    username=username)
            return jsonify({'access_token': token,
                            'username': username})
    return abort(403)


@hello_world.route('/settings', methods=['GET'])
@debug_only
def get_settings():
    return render_template('settings.html')


@hello_world.route('/settings-table', methods=['POST'])
@roles_required('admin')
def get_settings_table():
    s = {}
    for k, v in settings.items():
        if is_jsonable(v):
            s[k] = v
    app_settings = [{'key': i, 'value': j} for i, j in s.items()]
    app_settings.sort(key=lambda k: k['key'])
    return render_template('settings_table.html', app_settings=app_settings)


def is_jsonable(v):
    try:
        json.dumps(v)
    except Exception:
        return False
    return True
