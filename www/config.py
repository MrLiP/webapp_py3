#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Lip'

# 通常，一个web app在运行时都需要读取配置文件，比如数据库的用户名、口令等，在不同的环境中运行时，web app可以通过读取不同的配置文件来获得正确的配置
# 由于Python本身语法简单，完全可以直接用Python源代码来实现配置，而不需要再解析一个单独的.properties或者.yaml等配置文件
# 默认的配置文件应该完全符合本地开发环境，这样，无需任何设置，就可以立刻启动服务器。
# 我们把默认的配置文件命名为config_default.py：

# 但是，如果要部署到服务器时，通常需要修改数据库的host等信息，直接修改config_default.py不是一个好办法
# 更好的方法是编写一个config_override.py，用来覆盖某些默认设置：

# 把config_default.py作为开发环境的标准配置，把config_override.py作为生产环境的标准配置
# 我们就可以既方便地在本地开发，又可以随时把应用部署到服务器上。

# 应用程序读取配置文件需要优先从config_override.py读取。为了简化读取配置文件，可以把所有配置读取到统一的config.py中：

# config.py

import config_default

class Dict(dict):
    '''
    Simple dict but support access as x.y style.
    '''
    def __init__(self, names=(), values=(), **kw):
        super(Dict, self).__init__(**kw)
        # zip() 函数用于将可迭代的对象作为参数，将对象中对应的元素打包成一个个元组，然后返回由这些元组组成的列表
        for k, v in zip(names, values):
            self[k] = v

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Dict' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value

def merge(defaults, override):
    r = {}
    for k, v in defaults.items():
        # 当 k 出现在 override 中，优先取 override 的值
        if k in override:
            # 若 v 为字典，再度调用 merge() 函数，作递归
            if isinstance(v, dict):
                r[k] = merge(v, override[k])
            else:
                r[k] = override[k]
        else:
            r[k] = v
    return r

# 实现xxx.key的取值功能
def toDict(d):
    D = Dict()
    for k, v in d.items():
        # d 内部有字典时，调用递归
        D[k] = toDict(v) if isinstance(v, dict) else v
    return D

configs = config_default.configs

try:
    import config_override
    configs = merge(configs, config_override.configs)
except ImportError:
    pass

configs = toDict(configs)