# coding=utf-8

import os
import logging

from flask import Blueprint, request, abort, jsonify
from sqlalchemy import or_
import random, string
import zipfile
import shutil
import docker
import datetime

from spiderhub import db, settings
from spiderhub.models import Spider
from spiderhub.utils import get_meta_from_pagination

log = logging.getLogger(__name__)

spider_resource = Blueprint('spider', __name__)


@spider_resource.route('/spiders', methods=['GET'])
# 获取爬虫列表
def get_spider_list():
    page = int(request.args.get("page", default=1))
    per_page = request.args.get("per_page", default=10)
    pagination = Spider.query.order_by(Spider.id.desc()).paginate(page, per_page, error_out=False)
    meta = get_meta_from_pagination(pagination)
    spider_list = [i.to_dict() for i in pagination.items]
    status_list = get_spiders_status([{'id': i['id']} for i in spider_list])
    for i in range(len(status_list)):
        spider_list[i]['status'] = status_list[i]['status']

    return jsonify({'meta': meta, 'data': spider_list})


@spider_resource.route('/spiders/<key_mark>', methods=['GET'])
# 模糊查询
def search_spider(key_mark):
    all_spiders = Spider.query.filter(
        or_(Spider.name.like("%" + key_mark + "%") if key_mark is not None else "",
            Spider.description.like("%" + key_mark + "%") if key_mark is not None else "")
    ).all()

    spider_list = list()
    if all_spiders:
        for i in all_spiders:
            dict_one = i.to_dict()
            spider_list.append(dict_one)
        status_list = get_spiders_status([{'id': i['id']} for i in spider_list])
        for i in range(len(status_list)):
            spider_list[i]['status'] = status_list[i]['status']

    total = len(spider_list)
    return jsonify({'data': spider_list, 'total': total})


@spider_resource.route('/spiders/<spider_id>', methods=['GET'])
# 根据id获取爬虫的信息
def get_spider(spider_id):
    spider = Spider.query.filter_by(id=spider_id).first()
    if spider is not None:
        spider_dict = spider.to_dict()
        return jsonify({'data': spider_dict})
    return abort(404)


@spider_resource.route('/spiders/<spider_id>', methods=['DELETE'])
# 根据id删除数据库的爬虫信息
def delete_spider(spider_id):
    spider = Spider.query.filter_by(id=spider_id).first()
    if spider is not None:
        db.session.delete(spider)
        db.session.commit()
        return "delete success!"
    return abort(404)


@spider_resource.route('/spiders/<spider_id>/remove', methods=['DELETE'])
# 根据id删除服务器端爬虫文件
def delete_spider_file(spider_id):
    spider = Spider.query.filter_by(id=spider_id).first()
    if spider is not None:
        workspace = os.path.join(settings['data_dir'], 'workspace', spider.workspace)
        shutil.rmtree(workspace)
        return "remove success!"
    return abort(404)


@spider_resource.route('/spiders', methods=['POST'])
# 在数据库添加新的爬虫信息
def create_spider():
    data = request.json
    if data is not None:
        spider = Spider.from_dict(data)
        # TODO: 随机一个10位的字符串（a-zA-Z0-9）
        workspace_id = random_name()
        spider.workspace = workspace_id
        db.session.add(spider)
        db.session.commit()
        return jsonify(spider.to_dict())
    return abort(400)


def random_name():
    return ''.join(random.choice(string.digits + string.ascii_letters) for _ in range(10))


@spider_resource.route('/spiders/<spider_id>', methods=['PUT'])
# 根据id修改爬虫信息
def update_spider(spider_id):
    spider = Spider.query.filter_by(id=spider_id).first()
    if spider is not None:
        spider.update_by_dict(request.json)
        db.session.commit()
        return "update success！"
    return abort(400)


@spider_resource.route('/spiders/<spider_id>/workspace', methods=['POST'])
# 根据已有id上传爬虫.zip文件
def upload_spider(spider_id):
    spider = Spider.query.filter_by(id=spider_id).first()
    if spider is None:
        return abort(404)
    workspace = os.path.join(settings['data_dir'], 'workspace', spider.workspace)
    if not os.path.exists(workspace):
        os.makedirs(workspace)
    f = request.files['file']
    if f.filename.endswith('.zip'):
        temp_dir = os.path.join(settings['data_dir'], 'workspace', 'temp_dir')
        temp_zip_file = os.path.join(temp_dir, spider.workspace + '.zip')
        temp_workspace = os.path.join(temp_dir, spider.workspace)
        try:
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            f.save(temp_zip_file)
            fz = zipfile.ZipFile(temp_zip_file, 'r')
            if not os.path.exists(temp_workspace):
                os.makedirs(temp_workspace)
            fz.extractall(temp_workspace)
            fz.close()
            del_files(workspace)
            copy_files(temp_workspace, workspace)
            return "upload success!"
        except Exception:
            raise
        finally:
            shutil.rmtree(temp_workspace, ignore_errors=True)
            if os.path.exists(temp_zip_file):
                os.remove(temp_zip_file)
    return abort(400)


@spider_resource.route('/spiders/<spider_id>/workdirectory', methods=['POST'])
# 根据已有id上传工作目录
def upload_directory(spider_id):
    spider = Spider.query.filter_by(id=spider_id).first()
    if spider is None:
        return abort(404)
    workspace = os.path.join(settings['data_dir'], 'workspace', spider.workspace)
    if not os.path.exists(workspace):
        os.makedirs(workspace)
    f = request.files['file']
    savefile = os.path.abspath(os.path.join(workspace, *os.path.split(f.filename)[1:]))
    if not savefile.startswith(workspace + '/'):
        return abort(403)
    os.makedirs(os.path.dirname(savefile), exist_ok=True)
    f.save(savefile)
    return "uploaded!"


@spider_resource.route('/spiders/<spider_id>/beforeupload', methods=['DELETE'])
# 上传之前删除原文件夹下的所有文件
def beforeupload(spider_id):
    spider = Spider.query.filter_by(id=spider_id).first()
    if spider is not None:
        workspace = os.path.join(settings['data_dir'], 'workspace', spider.workspace)
        del_file(workspace)
        return "ok"
    return abort(404)


def del_file(path):
    ls = os.listdir(path)
    for f in ls:
        filepath = os.path.join(path, f)  # 将文件名映射成绝对路劲
        if os.path.isfile(filepath):  # 判断该文件是否为文件或者文件夹
            os.remove(filepath)  # 若为文件，则直接删除
            print(str(filepath) + " removed!")
        elif os.path.isdir(filepath):
            shutil.rmtree(filepath, True)  # 若为文件夹，则删除该文件夹及文件夹内所有文件
            print("dir " + str(filepath) + " removed!")


@spider_resource.route('/spiders/<spider_id>/<shm_size>/<flag>/run', methods=['POST'])
# 在容器里运行爬虫
def spider_run(spider_id, shm_size, flag):
    # 约定每一个spider.workspace下的spider.py为爬虫文件，requirements.txt为依赖文件
    if flag == 'True':
        spider = Spider.query.filter_by(id=spider_id).first()
        spider.run_flag = 'True'
        runspider(spider_id, shm_size)
    return 'stopped!'


def runspider(spider_id, shm_size):
    # 约定每一个spider.workspace下的spider.py为爬虫文件，requirements.txt为依赖文件
    spider = Spider.query.filter_by(id=spider_id).first()
    if spider is not None:
        if spider.run_flag == 'True':
            workspace = os.path.join(settings['data_dir'], 'workspace', spider.workspace)
            spider_path = os.path.join(workspace + '/spider.py')
            re_path = os.path.join(workspace + '/requirements.txt')
            config_path = os.path.join(workspace + '/config.py')

            if os.path.exists(spider_path):
                # 先找container是否存在，再判断是否在运行中，根据不同情况做出不同操作
                client = docker.from_env()
                thisimage = 'jadbin/xpaw'
                thiscommand = command(re_path, config_path)
                container_name = 'spider_' + str(spider_id)
                spider.docker_container = container_name
                db.session.commit()
                params = dict(image=thisimage, command=thiscommand, detach=True, tty=True,
                              name=container_name,
                              volumes={workspace: {'bind': '/opt/workspace', 'mode': 'rw'}})
                if shm_size:
                    params['shm_size'] = shm_size
                try:
                    container = client.containers.get(container_name)
                    log.info('拿到容器' + str(container_name))

                except:
                    client.containers.run(**params)


                else:
                    log.info(str(container_name) + '的状态：' + container.status)
                    if container.status == "running":
                        log.info('正在运行')
                        # return abort(403)
                    else:
                        container.remove()
                        log.info('# {} {}'.format(workspace, container_name))
                        container = client.containers.run(**params)
                        if spider.set_time:
                            tomorrow_date = get_day_zero_time(datetime.datetime.now()) + datetime.timedelta(days=1)
                            tomorrow_zero_time = get_day_zero_time(tomorrow_date)
                            spider.next_time = tomorrow_zero_time + datetime.timedelta(hours=spider.set_time)
                            db.session.commit()
                            log.info(str(spider.id) + '下次运行的时间' + str(spider.next_time))
                        else:
                            if spider.interval:
                                nowtime = datetime.datetime.now()
                                spider.next_time = nowtime + datetime.timedelta(seconds=spider.interval)
                                db.session.commit()
                                log.info(str(spider.id) + '下次运行的时间' + str(spider.next_time))
                log.debug(str(spider.id) + '运行结束')
                return "run"
        return 'stopped!'

    return abort(404)


def get_day_zero_time(date):
    """根据日期获取当天凌晨时间"""
    if not date:
        return 0
    date_zero = datetime.datetime.now().replace(year=date.year, month=date.month,
                                                day=date.day, hour=0, minute=0, second=0)
    return date_zero


@spider_resource.route('/spiders/<spider_id>/status', methods=['GET'])
# 返回一个json，包括爬虫运行状态，启动时间，已经运行的时间，通过docker接口获取
def get_spider_status(spider_id):
    spider = Spider.query.filter_by(id=spider_id).first()
    if spider is not None:
        if spider.docker_container is not None:
            client = docker.from_env()
            container = client.containers.get(spider.docker_container)
            status = container.status
            # container_dict=container.stats(decode=True,stream=True)
            return status
        return ('exited')

    return abort(404)


@spider_resource.route('/spiders/status', methods=['GET'])
# 返回json列表，包括所有爬虫的状态
def spider_status_list():
    page = int(request.args.get("page", default=1))
    per_page = request.args.get("per_page", default=10)
    pagination = Spider.query.order_by(Spider.id.desc()).paginate(page, per_page, error_out=False)
    spider_list = [i.to_dict() for i in pagination.items]
    status_list = get_spiders_status([{'id': i['id']} for i in spider_list])

    return jsonify(status_list)


def get_spiders_status(id_list):
    spider_dict = []
    for item in id_list:
        spider = Spider.query.filter_by(id=item['id']).first()
        if spider is not None:
            if spider.docker_container is not None:
                client = docker.from_env()
                container = client.containers.get(spider.docker_container)
                item['status'] = container.status
                spider_dict.append({'id': item['id'], 'status': item['status']})
            else:
                spider_dict.append({'id': item['id'], 'status': 'exited'})
        else:
            spider_dict.append({'id': item['id'], 'status': None})
    return spider_dict


@spider_resource.route('/spiders/<spider_id>/stop', methods=['POST'])
# 停止正在运行的爬虫
def stop_spider(spider_id):
    spider = Spider.query.filter_by(id=spider_id).first()
    if spider is not None:
        client = docker.from_env()
        container = client.containers.get(spider.docker_container)
        container.stop(timeout=0)
        spider.run_flag = 'false'
        db.session.commit()
        return 'stop'

    return abort(404)


# 删除非指定的文件
def del_files(dir, topdown=True):
    for root, dirs, files in os.walk(dir, topdown):
        for name in files:
            os.remove(os.path.join(root, name))


# 复制一个目录下所有文件到指定目录
def copy_files(sourceDir, targetDir):
    for file in os.listdir(sourceDir):
        sourceFile = os.path.join(sourceDir, file)
        targetFile = os.path.join(targetDir, file)
        if os.path.isfile(sourceFile):
            open(targetFile, "wb").write(open(sourceFile, "rb").read())


def command(path1, path2):
    re_str = 'pip install -r /opt/workspace/requirements.txt'
    crawl_str = 'xpaw crawl {} /opt/workspace/spider.py'.format(
        '-c /opt/workspace/config.py' if os.path.exists(path2) else '')
    if os.path.exists(path1):
        thiscommand = '{} && {}'.format(re_str, crawl_str)
    else:
        thiscommand = crawl_str

    return thiscommand


@spider_resource.route('/spiders/<spider_id>/time', methods=['GET'])
def get_time(spider_id):
    spider = spider = Spider.query.filter_by(id=spider_id).first()
    if spider is not None:
        nowtime = datetime.datetime.now()
        next_time = nowtime + datetime.timedelta(seconds=spider.interval)
        return jsonify(
            {'now_time': nowtime.strftime("%Y-%m-%d %H:%M:%S"), 'next_time': next_time.strftime("%Y-%m-%d %H:%M:%S")})
    else:
        return abort(404)


@spider_resource.route('/spiders/test', methods=['GET'])
def start(spider_id):
    return 'ok'
