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

class CustomContext(object):
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
                return lambda ip: obj
            return obj
        return None

    def isSelfContainable(self, name):
        return False

class Interpreter(object):
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
            if not hasattr(res, '__iter__'):
                res = [res]

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
        return self.f(**params)

def handleTagExceptions(f):
    def wrapper(self, ip):
        try:
            return f(self, ip)
        except TagAttributeMissing, e:
            message = '[required attribute "%s" is missing]' % e.message
        except TagNameInvalid, e:
            if e.message:
                message = '[tag name "%s" invalid]' % e.message
            else:
                message = '[missing tag name]'
        return [message]
    return wrapper

class Template(object):
    ''' object for rendering markup which can be extended about parameters and functions

    string based methods has to start with 'm' and continue with upper case letter
    all parameters are converted to unicode
    and should return list or unicode
    e.g.
    def mHello(self, name):
        return 'Hello ' + name
    '''
    def __init__(self, code):
        self.interpreter = Interpreter(code)

    def render(self, **kwargs):
        context = self.createContext(kwargs)
        self.interpreter.setContext(context)
        return self.interpreter.eval()

    def createContext(self, params):
        builtins = {}
        builtins.update(self._getParameters(params))
        builtins.update(self._getTemplateFunctions())
        builtins.update(self._getStringBasedMethods())
        return CustomContext(self.interpreter, builtins)

    def _getParameters(self, params):
        params = dict(('$'+k, v) for k, v in params.items())
        params.update({
            '(': u'[',
            ')': u']',
            'Sp': u' ',
        })
        return params

    def _getTemplateFunctions(self):
        return {
             'If': self.If,
             'List': self.List,
             'Split': self.Split,
             'PairTag': self.PairTag,
             'EmptyTag': self.EmptyTag,
         }

        return self.interpreter.eval()

    def _getStringBasedMethods(self):
        #find all methods starting with m[A-Z].*
        hasProperNameFormat = lambda k: len(k) > 2 and k[0] == 'm' and k[1].isupper()
        templateMethods = ((k[1:], getattr(self, k)) for k in dir(self) if callable(getattr(self, k)) and hasProperNameFormat(k))
        return dict((name, MethodWrapper(method)) for name, method in templateMethods)

    def List(self, ip):
        seq = ip.getValue('Seq', [])
        sep = ip.getString('Sep')
        if seq:
            ip.setContext(CustomContext(self.interpreter, {
                #do not use for styling, css 2.0 is powerfull enough
                '$Even':  lambda ip: i % 2 == 1,
                '$First': lambda ip: i == 0,
                '$Item':  lambda ip: x,
                '$Last':  lambda ip: i+1 == len(seq),
                '$Odd':   lambda ip: i % 2 == 0,
                '$Order': lambda ip: i+1,
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
        def parseAttributes(attributeString):
            attributes = (a for a in attributeString.split(','))
            attributes = (a.strip() for a in attributes)
            attributes = (a for a in attributes if a)
            return attributes

        def evaluateAttributes(attributes):
            return [(a, ip.getString(a)) for a in attributes]

        def evaluateAttributeList(listName):
            attrString = ip.getString(listName)
            attrList = parseAttributes(attrString)
            return evaluateAttributes(attrList)

        requiredPairs = evaluateAttributeList('Required')
        missingRequired = [a for a, v in requiredPairs if not v]
        if missingRequired:
            raise TagAttributeMissing(missingRequired[0])
        optionalPairs = evaluateAttributeList('Optional')
        return list(chain(requiredPairs, optionalPairs))

    def _getTagName(self, ip):
        name = ip.getString('Name').strip()
        if not TAG_NAME_RE.match(name):
            raise TagNameInvalid(name)
        return name

    @handleTagExceptions
    def PairTag(self, ip):
        name = self._getTagName(ip)
        attributes = self._getTagAttributes(ip)
        content = ip.getValue('@', [])
        return list(chain(('<', name, joinAttributes(attributes), '>'), content, ('</', name, '>')))

    @handleTagExceptions
    def EmptyTag(self, ip):
        name = self._getTagName(ip)
        attributes = self._getTagAttributes(ip)
        return ['<', name, joinAttributes(attributes), '/>']

TAG_NAME_RE = re.compile(r'^[a-zA-Z0-9]+(:[a-zA-Z0-9]+)?$')

class TagFormatError(Exception):
    def __init__(self, message):
        Exception.__init__(self)
        self.message = message

class TagNameInvalid(TagFormatError): pass
class TagAttributeMissing(TagFormatError): pass

def joinAttributes(attributes):
    return ''.join(' %s="%s"' % (a, escapeHtml(v))
        for a, v in attributes if v)


def escapeHtml(s):
    s = s.replace('&', '&amp;')
    s = s.replace('"', '&quot;')
    s = s.replace('>', '&gt;')
    s = s.replace('<', '&lt;')
    return s

