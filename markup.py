#encoding: utf-8

'''
Markup Template system
invented by Tomas Novotny as part of extbrain project http://extbrain.felk.cvut.cz/
implemented by Frantisek Jahoda

Targeted features:
    1. as simple syntax as possible
    2. extensible by custom functions
        2a. user can compose custom objects
    3. placeholders
    4. own templates definitions
    5. sand boxed (safe for use)
    6. debugging functions

Examples:

[import [guideline]]

[tr[Notes]]

[for list=[[getPhones [nokia_se40]] sep=[, ]] [
    [link target=[[url]] [[caption]]]
]]

[getPhones [nokia_se40]]

[= formatNotes=[
    [for list=[[getPhones [[@]]] sep=[, ]] [
        [link target=[[url]] [[caption]]]
    ]]
]]

Grammar:
    FILE = CONTENT
    CONTENT = [STR | BLOCK]*
    BLOCK = '[', INDENT, [PARAMS]*, ']'
    PARAMS = IDENT, '=[', CONTENT, ']'
           | '=[', CONTENT, ']'

'''

from itertools import chain
from collections import deque
import unittest
import inspect
import re
import unittest


class MarkupBlock(object):
    def __init__(self, name, params=None):
        self.name = name
        self.params = params or {}

    def __eq__(self, o):
        return isinstance(o, MarkupBlock) and self.name == o.name and self.params == o.params

    def __repr__(self):
        return 'use(%s, %s)' % (self.name, self.params)

class MarkupSyntaxError(Exception):
    def __init__(self, msg, lineno, pos, line, filename):
        Exception.__init__(self, msg)
        self.msg = msg
        self.lineno = lineno
        self.pos = pos
        self.line = line
        self.filename = filename

    def __str__(self):
        return '%s\n  File "%s", line %d\n    %s\n    %s' % (self.msg, self.filename, self.lineno, self.line, ' '*(self.pos - 1) + '^')

class Parser:
    RE_INDENT = re.compile('[a-zA-Z0-9_\.=@\!]')
    RE_PARAM = re.compile('[a-zA-Z0-9_\:]')

    class EndOfLineType:
        def __str__(self):
            return 'end of line'

    EOF = EndOfLineType()

    def __init__(self, s, filename='<stdin>'):
        self.inputStr = s
        self.index = 0
        self.brackets = 0
        self.lines = s.split('\n')
        self.lineno = 1
        self.pos = 1
        self.filename = filename

    def parse(self):
        self.brackets = 0
        return self.parseContent()

    def error(self, msg):
        raise MarkupSyntaxError(msg, self.lineno, self.pos, self.lines[self.lineno - 1], self.filename)

    def parseContent(self):
        content = []
        while True:
            skip = self.readUntil('[]')
            if skip:
                content.append(skip)
            current = self.getCurrent()
            if current == ']':
                if self.brackets == 0:
                    self.error('unexpected close bracket')
                return content
            elif current == '[':
                self.next()
                if self.getCurrent() == '*':
                    self.parseComment()
                else:
                    content.append( self.parseBlock() )
            else:
                if self.brackets != 0:
                    self.error('unbalanced brackets')
                return content

    def parseComment(self):
        while True:
            self.readUntil('*')
            self.next()
            current = self.getCurrent()
            if current == ']':
                self.next()
                break
            elif current == self.EOF:
                self.error('unfinished comment')


    def parseBlock(self):
        name = self.readWhileRe(self.RE_INDENT)
        if not name:
            self.error('no name')
        params = {}
        while True:
            self.readSpace()
            pname = '@'
            current = self.getCurrent()
            if current == ']':
                self.next()
                break
            elif current != '[':
                pname = self.readWhileRe(self.RE_PARAM)
                self.check('=')
                self.next()

            self.check('[')
            self.brackets += 1
            self.next()
            params[pname] = self.parseContent()
            self.next()
            self.brackets -= 1
        return MarkupBlock(name, params)

    def check(self, char):
        if self.getCurrent() != char:
            self.error('expects char "%s" found "%s"' % (char, self.getCurrent()))

    def getCurrent(self):
        return self.inputStr[self.index] if self.index < len(self.inputStr) else self.EOF

    def next(self):
        self.pos += 1
        if self.getCurrent() == '\n':
            self.pos = 1
            self.lineno += 1
        self.index += 1

    def read(self, whileCond):
        read = []
        while True:
            current = self.getCurrent()
            if current != self.EOF and whileCond(current):
                read.append(current)
                self.next()
            else:
                return ''.join(read)

    def readUntil(self, chars):
        return self.read(lambda c: c not in chars)

    def readWhileRe(self, re):
        return self.read(lambda c: re.match(c))

    def readSpace(self):
        return self.read(lambda c: c.isspace())


class BaseValue(object):
    pass

class StringValue(BaseValue):
    def __init__(self, s):
        super(StringValue, self).__init__()
        self.s = s

    def __call__(self, ip):
        return self.s if hasattr(self.s, '__iter__') else [self.s]

    def __repr__(self):
        return '"%s"' % self.s

class BlockCollection(BaseValue):
    def __init__(self, blocks):
        super(BlockCollection, self).__init__()
        self.blocks = blocks

    def __call__(self, ip):
        res = chain(*[b(ip) for b in self.blocks])
        return list(res)

    def __repr__(self):
        return '[%s]' % ', '.join(repr(b) for b in self.blocks)

class UseBlock(BaseValue):
    def __init__(self, name, default):
        super(UseBlock, self).__init__()
        self.name = name
        self.default = default

    def __call__(self, ip):
        blocks, context = ip.find(self.name)
        if blocks:
            res = ip.useBlock(self.name, blocks, context)
        else:
            res = self.default(ip)
        return res

    def __repr__(self):
        return '[%s|%s]' % (self.name, self.default)

class DefineBlock(BaseValue):
    def __init__(self, params, content):
        super(DefineBlock, self).__init__()
        self.params = params
        self.content = content

    def __call__(self, ip):
        ip.setContext(Context(self.params))
        value = self.content(ip)
        ip.delContext()
        return value

    def __repr__(self):
        return '[def %s %s]' % (', '.join('%s=%s' % (p, v) for p, v in self.params.items()), self.content)

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
    MISSING_MSG = '[%s not found]'
    #greater limit than python stack size will lead to exceptions
    RECURRENCE_LIMIT = 30

    def __init__(self, markup, builtins):
        self.markup = Parser(markup).parse()
        self.context = deque([CustomContext(builtins)])
        self.visited = set()
        self.useCount = 0

    def eval(self):
        ast = self.translate(self.markup)
        return ''.join(unicode(s) for s in ast(self))

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

    def translate(self, blocks):
        if isinstance(blocks, list):
            isDefinition = lambda b: isinstance(b, MarkupBlock) and ':' in b.params
            definitions = [b for b in blocks if isDefinition(b)]
            usages = [b for b in blocks if not isDefinition(b)]
            content = self.translateContent(usages)
            if definitions:
                return DefineBlock(dict((b.name, self.translateDefinition(b)) for b in definitions), content)
            else:
                return content

    RE_WHITESPACE = re.compile(r'[\r\n\t ]+')
    def translateContent(self, blocks):
        def replaceSpace(s):
            #replace longer whitespace with one space
            return self.RE_WHITESPACE.sub(' ', s)

        def stripString(b, isFirst, prevString):
            if isFirst:
                b = b.lstrip()
                if not b:
                    #skip first string if it is whitespace
                    return None
            elif prevString:
                if b.isspace():
                    #skip whitespace after any string
                    return None
                else:
                    #join following strings
                    b = prevString + b
                    seq.pop()
            return StringValue(replaceSpace(b))

        seq = []
        for b in blocks:
            if isinstance(b, basestring):
                item = stripString(b, not seq, seq[-1].s if seq and isinstance(seq[-1], StringValue) else None)
                if item is None:
                    continue
            else:
                useBlock = UseBlock(b.name, StringValue(self.MISSING_MSG % b.name))
                if b.params:
                    params = dict((p, self.translate(value)) for p, value in b.params.items())
                    item = DefineBlock(params, useBlock)
                else:
                    item = useBlock
            seq.append(item)
        if seq and isinstance(seq[-1], StringValue):
            s = seq[-1].s.rstrip()
            if not s:
                seq.pop()
            else:
                seq[-1].s = s
        if len(seq) == 1:
            return seq[0]
        else:
            return BlockCollection(seq)

    def translateDefinition(self, block):
        content = self.translate(block.params[':'])
        if len(block.params) > 1:
            res = DefineBlock(dict((p, UseBlock(p, self.translate(c))) for p, c in block.params.items()), content)
        else:
            res = content
        res.selfContainable = True
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

class MarkupTemplate():
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


def parse(s):
    return Parser(s).parse()

class TestParsing(unittest.TestCase):
    def testParse(self):
        use = MarkupBlock
        parseTree = [use('import', {'@': ['guideline']})]
        self.assertEqual(parse('[import [guideline]]'), parseTree)

        parseTree = [use('for', {
            'list': [use('enumerate', {'list': [use('customers')]})],
            'template': [use('order'), '. ', use('name')]
        })]
        self.assertEqual(parse('''[for list=[[enumerate list=[[customers]]]] template=[[order]. [name]]]'''), parseTree)
        self.assertRaises(MarkupSyntaxError, lambda: parse('[a x= []]'))


class TestInterpretation(unittest.TestCase):
    def testPlaceVariable(self):
        self.assertEqual(MarkupTemplate(name='world').render('Hello [name]!'), 'Hello world!')

    def testCallFunction(self):
        class TestingTemplate(MarkupTemplate):
            def mGreeting(self, name=u'John Doe'):
                return u'Hello %s!' % name
        self.assertEqual(TestingTemplate().render('Mr. White: [Greeting name=[Ms. Black]]'), 'Mr. White: Hello Ms. Black!')

    def testList(self):
        code = '''
        <ul>[List Seq=[[Literature]] [
            <li[*just an example better use css selector*][If [[Last]] Then=[[Sp]class="last"]]>[Order]. [Item]</li>
        ]]</ul>
        '''
        self.assertEqual(MarkupTemplate(Literature=[u'Shakespear', u'Čapek']).render(code), u'<ul><li>1. Shakespear</li><li class="last">2. Čapek</li></ul>')

    def testDefineTemplate(self):
        code = '''
        [Html :=[
            <html>[Header][Body]</html>
            ] Header=[
                <head><title>[Title]</title></head>
            ] Body=[
                <body>[@]</body>
            ]
        ]
        [Html Title=[New page] [Hello world!]]
        '''
        self.assertEqual(MarkupTemplate().render(code), '<html><head><title>New page</title></head><body>Hello world!</body></html>')

    def testNotFound(self):
        code = '[a] [b c=[d]]'
        self.assertEqual(MarkupTemplate().render(code), '[a not found] [b not found]')

    def testRecursion(self):
        code = '''
        [Greeting:=[Hello [name]!]]
        [Greeting name=[[name]]]
        '''
        self.assertEqual(MarkupTemplate().render(code), 'Hello [name not found]!')

    def testRecursion2(self):
        #note that same definition c is used multiple times while evaluating itself
        #see selfContainable property
        code = '''
        [c:=[[@]]]
        [c name=[a] [
            [c name=[[name]b] [
                [c name=[[name]c] [
                    Hello [name]!
                ]]
            ]]
        ]]
        '''
        self.assertEqual(MarkupTemplate().render(code), 'Hello abc!')

    def testRecursion3(self):
        #selfContainable property enables infinite recursion, this test ensures, that program has some limit on it
        code = '[c:=[[c]]][c]'
        self.assertEqual(MarkupTemplate().render(code), '[recurrence limit for c]')

    def testContent(self):
        code = '[user.nickname]([user.age])'
        self.assertEqual(MarkupTemplate(user={'nickname': 'spide', 'age': 26}).render(code), 'spide(26)')

    def testComment(self):
        code = 'aaa[*comment[*]bbb'
        self.assertEqual(MarkupTemplate().render(code), 'aaabbb')

    def testEscaping(self):
        self.assertEqual(MarkupTemplate().render('[lt]1[gt]'), '[1]')


if __name__ == '__main__':
    suite = unittest.TestSuite()
    suite.addTest(TestInterpretation('testRecursion'))
    #unittest.TextTestRunner().run(suite)
    unittest.main()


