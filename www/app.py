#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Lip'


'''
运行python app.py，Web App将在9000端口监听HTTP请求，并且对首页/进行响应：
'''

# Web 应用的本质：
# 1.浏览器发送一个HTTP请求；
# 2.服务器收到请求，生成一个HTML文档；
# 3.服务器把HTML文档作为HTTP响应的Body发送给浏览器；
# 4.浏览器收到HTTP响应，从HTTP Body取出HTML文档并显示。

# 底层代码由专门的服务器软件实现，我们用Python专注于生成HTML文档
# 所以，需要一个统一的接口，让我们专心用Python编写Web业务
# 这个接口就是WSGI：Web Server Gateway Interface

import logging; logging.basicConfig(level=logging.INFO)

import asyncio, os, json, time
from datetime import datetime

from aiohttp import web

# 客户端
async def index(request):
    # 同时去掉async 和 header 会使其变为文件下载
    text = '<h1>Awesome</h1>'
    # 加了content-type才会按html方式显示
    return web.Response(text=text, headers= {'content-type': 'text/html'})

# 用asyncio提供的@asyncio.coroutine可以把一个generator标记为coroutine类型
# 然后在coroutine内部用yield from调用另一个coroutine实现异步操作
# 为了简化并更好地标识异步IO，从Python 3.5开始引入了新的语法async和await
# async和await是针对coroutine的新语法，要使用新的语法，只需要做两步简单的替换：
# 1.把@asyncio.coroutine替换为async；
# 2.把yield from替换为await。

async def init(loop):
    app = web.Application(loop=loop)
    app.add_routes([web.get('/', index)])
    # 创建一个服务器地址，端口
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()