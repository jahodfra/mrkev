#encoding: utf-8

'''
Examples:

[import [guideline]]

[tr [Notes]]

[List seq=[[getPhones [nokia_se40]] sep=[, ]] [
    [Link target=[[item.url]] [[item.caption]]]
]]

[getPhones [nokia_se40]]

[formatNotes:=[
    [List seq=[[getPhones [[@]]] sep=[, ]] [
        [Link target=[[item.url]] [[item.caption]]]
    ]]
]]
'''

from itertools import chain
from collections import deque
import inspect
import re
from mrkev.parser import Parser
from mrkev.translator import BaseValue, Translator, Context

class CustomContext:
    def __init__(self, d):
        self.d = d

    def get(self, name):
        parts = name.split('.')
        fname, dictPath = parts[0], parts[1:]
        obj = self.d.get(fname)
        if obj:
            dictPath.reverse()
            while dictPath and obj:
                obj = obj.get(dictPath.pop(), None)
            if not callable(obj):
                if hasattr(obj, '__iter__'):
                    return lambda ip: obj
                else:
                    return lambda ip: [obj]
            return obj
        return None

class Interpreter:
    #greater limit than python stack size will lead to exceptions
    RECURRENCE_LIMIT = 30

    def __init__(self, markup, builtins):
        markup = Parser(markup).parse()
        self.ast = Translator().translate(markup)
        self.context = deque([CustomContext(builtins)])
        self.visited = set()
        self.useCount = 0

    def eval(self):
        return ''.join(unicode(s) for s in self.ast(self))

    def find(self, name):
        for c in self.context:
            if (c, name) not in self.visited:
                value = c.get(name)
                if value is not None:
                    return value, c
        return None, None

    def useBlock(self, name, blocks, context):
        if hasattr(blocks, 'selfContainable'):
            self.useCount += 1
            if self.useCount > self.RECURRENCE_LIMIT:
                return '[recurrence limit for %s]' % name
            res = blocks(self)
            self.useCount -= 1
        else:
            self.visited.add((context, name))
            res = blocks(self)
            self.visited.discard((context, name))
        return res

    def setContext(self, c):
        self.context.appendleft(c)

    def delContext(self):
        self.context.popleft()

    def getValue(self, name, ifMissing=None):
        v, context = self.find(name)
        if v:
            res = self.useBlock(name, v, context)
        else:
            res = ifMissing if ifMissing is not None else [MISSING_MSG % name]
        return res

    def getStringValue(self, name):
        return ''.join(unicode(s) for s in self.getValue(name))

    def getList(self, name):
        return self.getValue(name, [])

    def getBoolean(self, name):
        res = self.getValue(name, [False])
        return len(res) > 0 and res[0] is True

class MethodWrapper(BaseValue):
    def __init__(self, f):
        super(MethodWrapper, self).__init__()
        self.args = [n for n in inspect.getargspec(f).args if n != 'self']
        self.f = f

    def __call__(self, ip):
        formName = lambda a: a if a != 'content' else '@'
        params = dict((a, ip.getStringValue(formName(a))) for a in self.args)
        return [self.f(**params)]

class Template():
    def __init__(self, **kwargs):
        self.params = {
            'lt': u'[',
            'gt': u']',
            'NbSp': '&amp;',
            'Sp': ' ',
        }
        self.params.update(kwargs)

    def render(self, templateCode):
        #find all methods starting with m[A-Z].*
        callables = ((k[1:], MethodWrapper(getattr(self, k))) for k in dir(self) if callable(getattr(self, k)) and len(k) > 2 and k[0] == 'm' and k[1].isupper())
        builtins = {}
        builtins.update(self.params)
        builtins.update(callables)

        builtins['List'] = self.List
        builtins['If'] = self.If
        return Interpreter(templateCode, builtins).eval()

    def List(self, ip):
        seq = ip.getList('Seq')
        if seq:
            ip.setContext(Context({
                #do not use for styling, css 2.0 is powerfull enough
                'Even':  lambda ip: [i % 2 == 1],
                'First': lambda ip: [i == 0],
                'Item':  lambda ip: [x],
                'Last':  lambda ip: [i+1 == len(seq)],
                'Odd':   lambda ip: [i % 2 == 0],
                'Order': lambda ip: [i+1],
            }))
            res = [ip.getValue('@') for i, x in enumerate(seq)]
            ip.delContext()
            return list(chain(*res))
        else:
            return ip.getStringValue('IfEmpty')

    def If(self, ip):
        if ip.getBoolean('@'):
            return ip.getValue('Then', [])
        else:
            return ip.getValue('Else', [])


