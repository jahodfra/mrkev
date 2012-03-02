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
from mrkev.translator import UseBlock, DefineBlock, Translator

class CustomContext:
    def __init__(self, ip, d):
        self.d = d
        self.ip = ip

    def get(self, name):
        parts = name.split('.')
        fname, dictPath = parts[0], parts[1:]
        obj = self.d.get(fname)
        if obj:
            if callable(obj):
                obj = obj(self.ip)
            dictPath.reverse()
            while dictPath and obj:
                if isinstance(obj, list) and len(obj) == 1:
                    obj = obj[0]
                if hasattr(obj, 'get'):
                    obj = obj.get(dictPath.pop(), None)
                else:
                    return None
            if not callable(obj):
                if hasattr(obj, '__iter__'):
                    return lambda ip: obj
                else:
                    return lambda ip: [obj]
            return obj
        return None

    def isSelfContainable(self, name):
        return False

class Interpreter:
    #greater limit than python stack size will lead to exceptions
    RECURRENCE_LIMIT = 30
    MISSING_MSG = '[%s not found]'


    def __init__(self, markup):
        markup = Parser(markup).parse()
        self.ast = Translator().translate(markup)
        self.context = deque()
        self.visited = set()
        self.useCount = 0

    def setParams(self, builtins):
        self.context.appendleft(CustomContext(self, builtins))

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
        if isinstance(block, basestring):
            res = [block]

        elif isinstance(block, list):
            res = list(chain(*[self.interpretBlock(b) for b in block]))

        elif isinstance(block, UseBlock):
            blocks, context = self.find(block.name)
            if blocks:
                res = self.useBlock(block.name, blocks, context)
            elif block.default is not None:
                res = self.interpretBlock(block.default)
            else:
                res = [self.MISSING_MSG % block.name]

        elif isinstance(block, DefineBlock):
            self.setContext(block)
            res = self.interpretBlock(block.content)
            self.delContext()

        else:
            res = block(self)

        return res

    def useBlock(self, name, block, context):
        if context.isSelfContainable(name):
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

class MethodWrapper(object):
    def __init__(self, f):
        self.args = [n for n in inspect.getargspec(f).args if n != 'self']
        self.f = f

    def __call__(self, ip):
        formName = lambda a: a if a != 'content' else '@'
        params = dict((a, ip.getString(formName(a))) for a in self.args)
        return [self.f(**params)]

def handleTagExceptions(f):
    def wrapper(self, ip):
        try:
            return f(self, ip)
        except TagAttributeMissing, e:
            return ['[required attribute %s is missing]' % e.message]
        except TagNameMissing:
            return ['[tag name is missing]']
    return wrapper

class Template():
    def __init__(self, code):
        self.interpreter = Interpreter(code)

    def render(self, **kwargs):
        self.params = {
            '(': u'[',
            ')': u']',
            'Sp': u' ',
        }
        self.params.update(('#'+k, v) for k, v in kwargs.items())
        #find all methods starting with m[A-Z].*
        callables = ((k[1:], MethodWrapper(getattr(self, k))) for k in dir(self) if callable(getattr(self, k)) and len(k) > 2 and k[0] == 'm' and k[1].isupper())
        builtins = {
            'If': self.If,
            'List': self.List,
            'Split': self.Split,
            'PairTag': self.PairTag,
            'EmptyTag': self.EmptyTag,
        }
        builtins.update(self.params)
        builtins.update(callables)
        self.interpreter.setParams(builtins)

        return self.interpreter.eval()

    def List(self, ip):
        seq = ip.getValue('Seq', [])
        sep = ip.getString('Sep')
        if seq:
            ip.setContext(CustomContext(self.interpreter, {
                #do not use for styling, css 2.0 is powerfull enough
                '$Even':  lambda ip: [i % 2 == 1],
                '$First': lambda ip: [i == 0],
                '$Item':  lambda ip: [x],
                '$Last':  lambda ip: [i+1 == len(seq)],
                '$Odd':   lambda ip: [i % 2 == 0],
                '$Order': lambda ip: [i+1],
            }))
            if sep:
                res = []
                for i, x in enumerate(seq):
                    res.append(ip.getValue('@'))
                    if i + 1 != len(seq):
                        res.append(sep)
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

    def _getTagAttributes(self, ip):
        required = ip.getString('required')
        requiredAttributes = [a.strip() for a in required.split(',')]
        requiredPairs = [(attribute, ip.getString(attribute))
            for attribute in requiredAttributes
        ]
        for a, v in requiredPairs:
            if not v:
                raise TagAttributeMissing(a)
        optional = ip.getString('optional')
        optionalAttributes = [a.strip() for a in optional.split(',')]
        optionalPairs = [(attribute, ip.getString(attribute))
            for attribute in optionalAttributes
        ]
        return list(chain(requiredPairs, optionalPairs))

    def _getTagName(self, ip):
        name = ip.getString('name').strip()
        if not name:
            raise TagNameMissing()
        return name

    @handleTagExceptions
    def PairTag(self, ip):
        name = self._getTagName(ip)
        attributes = self._getTagAttributes(ip)
        if any(a == '@' for a, v in attributes):
            content = dict(attributes)['@']
            attributes = [(a, v) for a, v in attributes if a != '@']
        else:
            content = ip.getString('@')
        return [''.join(('<', name, joinAttributes(attributes), '>', content, '</', name, '>'))]

    @handleTagExceptions
    def EmptyTag(self, ip):
        name = self._getTagName(ip)
        attributes = self._getTagAttributes(ip)
        return [''.join(('<', name, joinAttributes(attributes), '/>'))]


class TagNameMissing(Exception):
    pass

class TagAttributeMissing(Exception):
    def __init__(self, message):
        Exception.__init__(self)
        self.message = message

def joinAttributes(attributes):
    return ''.join(' %s="%s"' % (a, escapeHtml(v))
        for a, v in attributes if v)


def escapeHtml(s):
    s = s.replace('&', '&amp;')
    s = s.replace('"', '&quot;')
    s = s.replace('>', '&gt;')
    s = s.replace('<', '&lt;')
    return s

