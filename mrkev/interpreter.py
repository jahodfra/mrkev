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
    [List seq=[[getPhones [[#]]] sep=[, ]] [
        [Link target=[[item.url]] [[item.caption]]]
    ]]
]]
'''

from itertools import chain
from collections import deque
import inspect
import re

from mrkev.parser import Parser
from mrkev.translator import CallBlock, CallParameter, BlockDefinition, BlockScope, Translator, formParameterName

class CustomContext(object):
    def __init__(self, ip, d):
        self.d = d
        self.ip = ip

    def get(self, name):
        parts = name.split('.')
        fname, dictPath = parts[0], parts[1:]
        obj = self.d.get(fname)
        if obj:
            if dictPath and callable(obj):
                obj = obj(self.ip)
            dictPath.reverse()
            while dictPath and obj:
                if isinstance(obj, list) and len(obj) == 1:
                    obj = obj[0]
                if hasattr(obj, 'get'):
                    obj = obj.get(dictPath.pop())
                else:
                    return None
            if not callable(obj):
                return lambda ip: obj
            return obj
        return None

class ErrorFormatter(object):
    def formatBlockMissing(self, name):
        return u'[{0} not found]'.format(name)

    def formatRecurrenceLimit(self, name, limit):
        return u'[recurrence limit for {0}]'.format(name)

class ErrorBlock(object):
    def __init__(self, msg):
        self.msg = msg

    def __unicode__(self):
        ''' print error to output
        '''
        return self.msg

    def __nonzero__(self):
        ''' getBoolean evaluates errors as False
        '''
        return False

class Interpreter(object):
    #greater limit than python stack size will lead to exceptions
    RECURRENCE_LIMIT = 30

    def __init__(self, ast, errorFormatter=None):
        self.ast = ast
        self.useCount = 0
        self.errorFormatter = errorFormatter or ErrorFormatter()
        self.currentLexicalScope = None
        self.blockScopes = deque()
        self.callScopes = deque()

    def evalToString(self):
        return ''.join(unicode(s) for s in self.eval(self.ast))

    def findBlock(self, block):
        for c in self.blockScopes:
            value = c.get(block.name)
            if value is not None:
                return value
        return None

    def findParameter(self, block):
        for callBlock, blockDef in self.callScopes:
            if blockDef is block.lexicalScope:
                #get last calling of the same block
                if block.inDefaultParameter:
                    #prevents call cycles in default parameters
                    return callBlock.get(block.name)
                else:
                    return  callBlock.get(block.name) or block.lexicalScope.get(block.name)
        return None

    def eval(self, block):
        if isinstance(block, basestring):
            #strings
            res = [block]

        elif isinstance(block, list):
            #block content
            res = list(chain(*[self.eval(b) for b in block]))

        elif isinstance(block, CallBlock):
            res = self.evalCallBlock(block)

        elif isinstance(block, CallParameter):
            blocks = self.findParameter(block)
            if not blocks:
                msg = self.errorFormatter.formatBlockMissing(block.name)
                return [ErrorBlock(msg)]
            res = self.eval(blocks)

        elif isinstance(block, BlockScope):
            self.addBlockScope(block)
            res = self.eval(block.content)
            self.removeBlockScope()

        else:
            res = block(self)
            if not hasattr(res, '__iter__'):
                res = [res]

        return res

    def evalCallBlock(self, block):
        name = block.name
        blockDef = self.findBlock(block)
        if not blockDef:
            msg = self.errorFormatter.formatBlockMissing(name)
            return [ErrorBlock(msg)]

        self.useCount += 1
        if self.useCount > self.RECURRENCE_LIMIT:
            return self.createRecurrenceLimit(name)

        if isinstance(blockDef, BlockDefinition):
            self.addCallScope(block, blockDef)
            res = self.eval(blockDef.content)
            self.removeCallScope()
        else:
            self.addCallScope(block, None)
            res = self.eval(blockDef)
            self.removeCallScope()

        self.useCount -= 1
        return res

    def createRecurrenceLimit(self, name):
        msg = self.errorFormatter.formatRecurrenceLimit(name, self.RECURRENCE_LIMIT)
        return [ErrorBlock(msg)]

    def addBlockScope(self, blockScope):
        self.blockScopes.appendleft(blockScope)

    def removeBlockScope(self):
        self.blockScopes.popleft()

    def addCallScope(self, blockCall, blockDefinition):
        self.callScopes.appendleft((blockCall, blockDefinition))

    def removeCallScope(self):
        self.callScopes.popleft()

    def getValue(self, name, ifMissing=None):
        res = self.eval(CallParameter(name, lexicalScope=None, inDefaultParameter=True))
        if ifMissing is not None and res and isinstance(res[0], ErrorBlock):
            res = ifMissing
        return res

    def getString(self, name):
        return ''.join(unicode(s) for s in self.getValue(name, []))

    def getBoolean(self, name):
        '''convert block to boolean

        unknown or empty -> False
        '''
        res = self.getValue(name)
        return len(res) > 0 and all(res)

    def getGetLastCallParameters(self):
        if self.callScopes:
            return self.callScopes[0][0].params.keys()
        else:
            return []

class MethodWrapper(object):
    def __init__(self, f):
        self.args = [n for n in inspect.getargspec(f).args if n != 'self']
        self.f = f

    def __call__(self, ip):
        formName = lambda a: formParameterName(a) if a != 'content' else '#'
        params = dict((a, ip.getString(formName(a))) for a in self.args)
        return self.f(**params)

class Template(object):
    ''' object for rendering markup which can be extended about parameters and functions

    string based methods has to start with 'm' and continue with upper case letter
    all parameters are converted to unicode
    and should return list or unicode
    e.g.
    def mHello(self, name):
        return 'Hello ' + name
    '''
    def __init__(self, code, errorFormatter=None):
        if isinstance(code, basestring):
            code = Parser(code).parse()
        code = Translator().translate(code)
        self.interpreter = Interpreter(code, errorFormatter=errorFormatter)

    def render(self, **kwargs):
        context = self.createContext(kwargs)
        self.interpreter.addBlockScope(context)
        return self.interpreter.evalToString()

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
             'html': TagGenerator(),
         }

    def _getStringBasedMethods(self):
        #find all methods starting with m[A-Z].*
        hasProperNameFormat = lambda k: len(k) > 2 and k[0] == 'm' and k[1].isupper()
        templateMethods = ((k[1:], getattr(self, k)) for k in dir(self) if callable(getattr(self, k)) and hasProperNameFormat(k))
        return dict((name, MethodWrapper(method)) for name, method in templateMethods)

    def List(self, ip):
        seq = ip.getValue('#Seq', [])
        sep = ip.getString('#Sep')
        if seq:
            ip.addBlockScope(CustomContext(self.interpreter, {
                #do not use for styling, css 2.0 is powerfull enough
                '$Even':  lambda _: i % 2 == 1,
                '$First': lambda _: i == 0,
                '$Item':  lambda _: x,
                '$Last':  lambda _: i+1 == len(seq),
                '$Odd':   lambda _: i % 2 == 0,
                '$Order': lambda _: i+1,
            }))
            if sep:
                res = []
                for i, x in enumerate(seq):
                    res.append(ip.getValue('#'))
                    if i + 1 != len(seq):
                        res.append(sep)
            else:
                res = [ip.getValue('#') for i, x in enumerate(seq)]
            ip.removeBlockScope()
            return list(chain(*res))
        else:
            return ip.getValue('#IfEmpty', [])

    def Split(self, ip):
        content = ip.getString('#')
        sep = ip.getString('#Sep')
        if sep:
            res = content.split(sep)
        else:
            res = [content]
        return res

    def If(self, ip):
        if ip.getBoolean('#'):
            return ip.getValue('#Then', [])
        else:
            return ip.getValue('#Else', [])

class TagGenerator:
    TAG_NAME_RE = re.compile(r'^[a-zA-Z0-9]+(:[a-zA-Z0-9]+)?$')

    def get(self, name):
        def wrapper(ip):
            attributes = ip.getGetLastCallParameters()
            if not self.TAG_NAME_RE.match(name):
                return '[tag name "%s" invalid]' % name
            attrList = [(a, ip.getString(a)) for a in attributes if a != '#']
            if '#' in attributes:
                content = ip.getString('#')
                return list(chain(('<', name, joinAttributes(attrList), '>'), content, ('</', name, '>')))
            else:
                return ['<', name, joinAttributes(attrList), '/>']
        return wrapper

def joinAttributes(attributes):
    return ''.join(' %s="%s"' % (a[1:], escapeHtml(v))
        for a, v in attributes if v)

def escapeHtml(s):
    s = s.replace('&', '&amp;')
    s = s.replace('"', '&quot;')
    s = s.replace('>', '&gt;')
    s = s.replace('<', '&lt;')
    return s

