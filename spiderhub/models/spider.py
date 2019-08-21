# coding=utf-8

from sqlalchemy import text as _text

from spiderhub import db


class Spider(db.Model):
    __tablename__ = 'spider'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(64))
    description = db.Column(db.String(255))
    workspace = db.Column(db.String(64))
    docker_container = db.Column(db.String(64))
    created_time = db.Column(db.DateTime, server_default=_text("CURRENT_TIMESTAMP"), default=db.func.now())
    updated_time = db.Column(db.DateTime, server_default=_text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), default=db.func.now(), onupdate=db.func.now())
    params = db.Column(db.String(255))
    set_time = db.Column(db.Integer)
    interval = db.Column(db.Integer)
    next_time = db.Column(db.DateTime, index=True)
    run_flag = db.Column(db.String(255), server_default=_text("''"))
