#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Lip'

# 正式开始web开发前，还需要编写一个 web 框架，为了简化 aiohttp 的重复性工作
# 从使用者的角度来说，aiohttp 相对比较底层，编写一个URL的处理函数需要如下几步：
# 第一步，编写一个用@asyncio.coroutine装饰的函数：
# @asyncio.coroutine
# def handle_url_xxx(request):
#     pass
# 第二步，传入的参数需要自己从request中获取：
# url_param = request.match_info['key']
# query_params = parse_qs(request.query_string)
# 最后，需要自己构造Response对象：
# text = render('template', data)
# return web.Response(text.encode('utf-8'))

# 我们需要利用框架处理，简化工作
# 因此，Web框架的设计是完全从使用者出发，目的是让使用者编写尽可能少的代码。
# 编写简单的函数而非引入request和web.Response还有一个额外的好处，就是可以单独测试，否则，需要模拟一个request才能测试。

import asyncio, os, inspect, logging, functools

from urllib import parse

from aiohttp import web
# apis是处理分页的模块,代码在本章页面末尾,请将apis.py放在www下以防报错
from apis import APIError

# @get和@post，要把一个函数映射为一个URL处理函数，我们先定义@get()：
# 定义装饰器@get，，，@get('/blog/{id}')
def get(path):
    '''
    Define decorator @get('/path')
    '''
    def decorator(func):
        # 把原始函数的__name__等属性复制到wrapper()函数中，否则，有些依赖函数签名的代码执行就会出错
        @ functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator
# 这样，一个函数通过@get()的装饰就附带了URL信息。
# @post与@get定义类似。
def post(path):
    '''
    Define decorator @post('/path')
    '''
    def decorator(func):
        @ functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator

# 定义RequestHandler需求的函数

def get_required_kw_args(fn):
    args = []
    # inspect 模块
    # inspect.signature(fn)将返回一个inspect.Signature类型的对象，值为fn这个函数的所有参数
    # inspect.Signature对象的paremerters属性是一个mappingproxy（映射）类型的对象，值为一个有序字典
    # 字典里的key为参数名，value是一个inspect.Parameter类型的对象，包含参数的各种信息
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        # inspect.Perameter对象的kind属性是一个_ParameterKind枚举类型的对象，值为这个参数的类型（可变参数，关键词参数，stc）
        # POSITIONAL_ONLY、VAR_POSITIONAL、KEYWORD_ONLY、VAR_KEYWORD、POSITIONAL_OR_KEYWORD
        # 分别代表着位置参数、可变参数、命名关键字参数、关键字参数等
        # inspect.Parameter对象的default属性：若该参数有默认值，返回其默认值，若无，返回一个inspect._empty类
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            # 当 fn 的输入参数是无默认值的命名关键词参数，添加到列表里
            args.append(name)
    return tuple(args)

def get_named_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            # 如果 fn 的输入参数是命名关键词参数，就添加到列表里
            args.append(name)
    return tuple(args)

def has_named_kw_args(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True

def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            # 输入参数类型为VAR_KEYWORD，返回True
            return True

def has_request_arg(fn):
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
    return found

# 定义RequestHandler
# URL处理函数不一定是一个coroutine，因此我们用RequestHandler()来封装一个URL处理函数
# RequestHandler是一个类，由于定义了__call__()方法，因此可以将其实例视为函数。
# RequestHandler目的就是从URL函数中分析其需要接收的参数，从request中获取必要的参数，调用URL函数
# 然后把结果转换为web.Response对象，这样，就完全符合aiohttp框架的要求：
class RequestHandler(object):

    def __init__(self,app,fn):
        self._app = app
        self._func = fn
        self._has_request_arg = has_request_arg(fn)
        self._has_var_kw_arg = has_var_kw_arg(fn)
        self._has_named_kw_args = has_named_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._required_kw_args = get_required_kw_args(fn)

    async def __call__(self, request):
        kw = None
        if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:
            if request.method == 'POST':
                if not request.content_type:
                    return web.HTTPBadRequest('Missing Content-Type.')
                ct = request.content_type.lower()
                # startswith() 方法用于检查字符串是否是以指定子字符串开头，如果是则返回 True，否则返回 False
                if ct.startswith('application/json'):
                    params = await request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest('JSON body must be object.')
                    kw = params
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    params = await request.post()
                    # 将 params 转化为 dict 字典格式
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)
            if request.method == 'GET':
                # 获取 request 中的 query_string 格式
                qs = request.query_string
                if qs:
                    kw = dict()
                    # parse_qs属于urlparse中解析网址的方法
                    # >>>dict([(k,v[0]) for k,v in urllib.parse.parse_qs(a).items()])
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]
        if kw is None:
            kw = dict(**request.match_info)
        else:
            if not self._has_var_kw_arg and self._named_kw_args:
                # remove all unamed kw:
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            # check named arg:
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v
        if self._has_request_arg:
            kw['request'] = request
        # check required kw:
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:
                    return web.HTTPBadRequest('Missing argument: %s' % name)
        logging.info('call with args: %s' % str(kw))
        try:
            r = await self._func(**kw)
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)

## 定义add_static函数，来注册static文件夹下的文件
def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)
    logging.info('add static %s => %s' % ('/static/', path))

## 定义add_route函数，来注册一个URL处理函数
def add_route(app, fn):
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
    logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    app.router.add_route(method, path, RequestHandler(app, fn))

## 定义add_routes函数，自动把handler模块的所有符合条件的URL函数注册了
def add_routes(app, module_name):
    #  rfind() 返回字符串最后一次出现的位置(从右向左查询)，如果没有匹配项则返回-1
    n = module_name.rfind('.')
    if n == (-1):
        mod = __import__(module_name, globals(), locals())
    else:
        name = module_name[n+1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    for attr in dir(mod):
        if attr.startswith('_'):
            continue
        fn = getattr(mod, attr)
        if callable(fn):
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path:
                add_route(app, fn)