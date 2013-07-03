from types import FunctionType
import sys, os, argparse

class classmethod_mc(type):
    def __new__(mcs, name, bases, dct):
        for k, v in dct.iteritems():
            if isinstance(v, FunctionType):
                dct[k] = classmethod(v)#staticmethod(lambda *args: v(ret, *args))
        ret = type.__new__(mcs, name, bases, dct)
        if hasattr(ret, '__init__') and ret.__init__ is not object.__init__: ret.__init__()
        return ret
class singleton(object):
    __metaclass__ = classmethod_mc

mydir = os.path.dirname(__file__)

def action(callback):
    return {'action': 'append_const', 'dest': 'actions', 'const': callback, 'default': []}
def run_actions(args):
    for action in args.actions:
        action()
def remove_none(lst):
    return filter(lambda x: x is not None, lst)

class chdir:
    def __init__(self, path):
        self.path = path
    def __enter__(self):
        self.old = os.getcwd()
        os.chdir(self.path)
    def __exit__(self, *args):
        os.chdir(self.old)
