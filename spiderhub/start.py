from spiderhub.models import Spider
import time, datetime
import requests
import logging
from spiderhub.blueprints import spider

from guniflask.bg_process import BgProcess

URL = 'localhost:8023/spiders/'

log = logging.getLogger(__name__)


class RunSpiderProcess(BgProcess):
    def run(self):
        while True:
            log.debug('start')
            nowtime = datetime.datetime.now()
            spiderlist = Spider.query.filter(nowtime > Spider.next_time)
            spider_dict = [i.to_dict() for i in spiderlist]
            for i in spider_dict:
                if(spider.get_spider_status(i['id'])=='running'):
                    log.debug(str(i['id'])+'的容器正在运行...')
                else:
                    spider.runspider(i['id'],i['params'])
                    log.debug('run_'+str(i['id']))
            log.debug('end')
            time.sleep(5)


