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
from mrkev.translator import BaseValue, StringValue, BlockCollection, UseBlock, DefineBlock, Translator

class Context(dict):
    def __hash__(self):
        return id(self)

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
    MISSING_MSG = '[%s not found]'


    def __init__(self, markup, builtins):
        markup = Parser(markup).parse()
        self.ast = Translator().translate(markup)
        self.context = deque([CustomContext(builtins)])
        self.visited = set()
        self.useCount = 0

    def eval(self):
        return ''.join(unicode(s) for s in self.interpretBlock(self.ast))

    def find(self, name):
        for c in self.context:
            if (c, name) not in self.visited:
                value = c.get(name)
                if value is not None:
                    return value, c
        return None, None

    def interpretBlock(self, block):
        if isinstance(block, StringValue):
            res = block.s if hasattr(block.s, '__iter__') else [block.s]

        elif isinstance(block, BlockCollection):
            res = list(chain(*[self.interpretBlock(b) for b in block.blocks]))

        elif isinstance(block, UseBlock):
            blocks, context = self.find(block.name)
            if blocks:
                res = self.useBlock(block.name, blocks, context)
            elif block.default is not None:
                res = self.interpretBlock(block.default)
            else:
                res = [self.MISSING_MSG % block.name]

        elif isinstance(block, DefineBlock):
            self.setContext(Context(block.params))
            res = self.interpretBlock(block.content)
            self.delContext()

        else:
            res = block(self)

        return res

    def useBlock(self, name, block, context):
        if hasattr(block, 'selfContainable'):
            self.useCount += 1
            if self.useCount > self.RECURRENCE_LIMIT:
                return '[recurrence limit for %s]' % name
            res = self.interpretBlock(block)
            self.useCount -= 1
        else:
            self.visited.add((context, name))
            res = self.interpretBlock(block)
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
            res = ifMissing if ifMissing is not None else [self.MISSING_MSG % name]
        return res

    def getString(self, name):
        return ''.join(unicode(s) for s in self.getValue(name, []))

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
        params = dict((a, ip.getString(formName(a))) for a in self.args)
        return [self.f(**params)]

class Template():
    def __init__(self, **kwargs):
        self.params = {
            '(': u'[',
            ')': u']',
            'Sp': u' ',
        }
        self.params.update(kwargs)

    def render(self, templateCode):
        #find all methods starting with m[A-Z].*
        callables = ((k[1:], MethodWrapper(getattr(self, k))) for k in dir(self) if callable(getattr(self, k)) and len(k) > 2 and k[0] == 'm' and k[1].isupper())
        builtins = {
            'List': self.List,
            'If': self.If,
        }
        builtins.update(self.params)
        builtins.update(callables)

        return Interpreter(templateCode, builtins).eval()

    def List(self, ip):
        seq = ip.getValue('Seq', [])
        sep = ip.getString('Sep')
        if seq:
            ip.setContext(CustomContext({
                #do not use for styling, css 2.0 is powerfull enough
                'Even':  lambda ip: [i % 2 == 1],
                'First': lambda ip: [i == 0],
                'Item':  lambda ip: [x],
                'Last':  lambda ip: [i+1 == len(seq)],
                'Odd':   lambda ip: [i % 2 == 0],
                'Order': lambda ip: [i+1],
            }))
            if sep:
                res = list(chain(*[(ip.getValue('@'), sep) for i, x in enumerate(seq)]))
            else:
                res = [ip.getValue('@') for i, x in enumerate(seq)]
            ip.delContext()
            return list(chain(*res))
        else:
            return ip.getValue('IfEmpty', [])

    def Split(self, ip):
        content = ip.getString('@')
        sep = ip.getString('Sep')
        if sep:
            res = content.split(sep)
        else:
            res = [content]
        return res

    def If(self, ip):
        if ip.getBoolean('@'):
            return ip.getValue('Then', [])
        else:
            return ip.getValue('Else', [])


