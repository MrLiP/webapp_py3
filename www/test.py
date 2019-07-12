import sys
import os
import random
import asyncio

import orm
from models import User,Blog,Comment

async def test(loop):
    await orm.create_pool(loop, user='www-data', password='www-data', db='awesome')
    u = User(name='Test', email='test%s@example.com' % random.randint(0,10000000), passwd='1234567890', image='about:blank')
    await u.save()
    # 添加到数据库后需要关闭连接池，否则会报错 RuntimeError: Event loop is closed
    orm.__pool.close()
    await orm.__pool.wait_closed()

#要运行协程，需要使用事件循环
if __name__ == '__main__':
        loop = asyncio.get_event_loop()
        loop.run_until_complete(test(loop))
        print('Test finished.')
        loop.close()