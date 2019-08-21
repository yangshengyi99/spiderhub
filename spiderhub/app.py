# coding=utf-8

import logging
from os import makedirs
from os.path import exists, join

from flask_sqlalchemy import SQLAlchemy

from guniflask.config import Config
from guniflask.security import JwtAuthManager

log = logging.getLogger(__name__)

config = Config()
db = SQLAlchemy()
jwt_manager = JwtAuthManager()


def make_settings(app, settings):
    """
    This function is invoked before initializing app.
    """

    settings['data_dir'] = join(settings['home'], '.data')
    if not exists(settings['data_dir']):
        makedirs(settings['data_dir'])


def init_app(app, settings):
    """
    This function is invoked before running app.
    """
