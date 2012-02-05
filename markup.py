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
from unittest import TestCase
import inspect
import re
import unittest

def interpretBlockContent(content, interpreter):
    return [part.apply(interpreter) if hasattr(part, 'apply') else part for part in content]


class MarkupBlock(object):
    def __init__(self, name, params=None):
        self.name = name
        self.params = params or {}

    def __eq__(self, o):
        return isinstance(o, MarkupBlock) and self.name == o.name and self.params == o.params

    def __repr__(self):
        return 'use(%s, %s)' % (self.name, self.params)

    def apply(self, interpreter):
        content = interpreter.getBlockContent(self.name)
        interpreter.setContext(self.name, self.params)
        if isinstance(content, BlockContent):
            res = u''.join(interpretBlockContent(content, interpreter))
        elif isinstance(content, (list, tuple)):
            res = content
        elif isinstance(content, (basestring, int, float)):
            res = unicode(content)
        elif callable(content):
            res = content(interpreter)
        else:
            raise AttributeError('block name=%s has unknown type %s' % (content, type(content)))
        interpreter.delContext()
        return res

    def get(self, k):
        return self.params.get(k)


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

class BlockContent(list):
    pass

class Parser:
    RE_INDENT = re.compile('[a-zA-Z0-9_\.=@]')
    RE_PARAM = re.compile('[a-zA-Z0-9_\:]')
    RE_WHITESPACE = re.compile(r'[\r\n\t ]+')

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
        def removeEndingSpace(content):
            if content and not isinstance(content[-1], MarkupBlock):
                end = content[-1].rstrip()
                if end:
                    content[-1] = end
                else:
                    del content[-1]

        content = BlockContent()
        first = True
        while True:
            if first:
                #remove leading whitespace
                self.readSpace()
                first = False
            skip = self.readUntil('[]')
            if skip:
                #replace longer whitespace with one space
                skip = self.RE_WHITESPACE.sub(' ', skip)
                content.append(skip)
            current = self.getCurrent()
            if current == ']':
                if self.brackets == 0:
                    self.error('unexpected close bracket')
                removeEndingSpace(content)
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
                removeEndingSpace(content)
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

def parse(s):
    return Parser(s).parse()

class Interpreter:
    MISSING_CONTENT = u'[not found]'
    def __init__(self, markup, builtins):
        self.markup = markup
        self.context = [builtins]

    def eval(self):
        return u''.join(interpretBlockContent(self.markup, self))

    def getBlockContent(self, name):
        names = name.split('.')
        fname, rname = names[0], names[1:]

        for c in self.context:
            if fname in c:
                obj = c[fname]
                while rname:
                    obj = obj.get(rname[0])
                    rname = rname[1:]
                    if not obj:
                        return u'[not found]'
                return obj
        return self.MISSING_CONTENT

    def setContext(self, name, c):
        self.context.insert(0, c)

    def delContext(self):
        del self.context[0]

    #TODO: should support default values
    def getValue(self, name):
        v = self.getBlockContent(name)
        if isinstance(v, BlockContent):
            #prevent recursion
            if name in self.context[0]:
                block = self.context[0][name]
                del self.context[0][name]
                v = interpretBlockContent(v, self)
                self.context[0][name] = block
            else:
                #TODO: block defining scope should prevent recursion
                v = interpretBlockContent(v, self)
        return v

    def getBooleanValue(self, name):
        v = self.getValue(name)
        return bool(v and v[0] is True)


    def getStringValue(self, name):
        return ''.join(self.getValue(name))


class MethodWrapper:
    def __init__(self, f):
        self.args = [n for n in inspect.getargspec(f).args if n != 'self']
        self.f = f

    def __call__(self, interpreter):
        params = dict((a, interpreter.getStringValue(a)) for a in self.args)
        return self.f(**params)


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
        builtins = dict((k, v) for k, v in chain(self.params.items(), callables))
        builtins['List'] = self.List
        builtins['If'] = self.If
        return Interpreter(parse(templateCode), builtins).eval()

    def List(self, interpreter):
        seq = interpreter.getValue('Seq')
        if seq and hasattr(seq[0], '__iter__') and len(seq[0]) > 0:
            items = seq[0]
            itemContext = {
                'Last':  lambda interpreter: itemContext['Order'] == len(items),
                'First': lambda interpreter: itemContext['Order'] == 1,
                'Even':  lambda interpreter: itemContext['Order'] % 2 == 0,
                'Odd':   lambda interpreter: itemContext['Order'] % 2 == 1,
            }
            interpreter.setContext('List', itemContext)
            res = []
            for i, x in enumerate(items):
                itemContext['Order'] = i + 1
                itemContext['Item'] = x
                res.append(interpreter.getStringValue('@'))
            interpreter.delContext()
            return ''.join(res)
        else:
            return interpreter.getStringValue('IfEmpty')

    def If(self, interpreter):
        if interpreter.getBooleanValue('@'):
            return interpreter.getStringValue('Then')
        return u''



class TestParsing(TestCase):
    def testParse(self):
        use = MarkupBlock
        parseTree = [use('import', {'@': ['guideline']})]
        self.assertEqual(parse('[import [guideline]]'), parseTree)

        parseTree = [use('for', {
            'list': [use('enumerate', {'list': [use('customers')]})],
            'template': [use('order'), '. ', use('name')]
        })]
        self.assertEqual(parse('''[for list=[[enumerate list=[[customers]]]] template=[
            [order]. [name]
        ]]'''), parseTree)
        self.assertRaises(MarkupSyntaxError, lambda: parse('[a x= []]'))


class TestInterpretation(TestCase):
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
            <li[If [[Last]] Then=[[Sp]class="last"]]>[Order]. [Item]</li>
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
        self.assertEqual(MarkupTemplate().render(code), '[not found] [not found]')

    def testRecursion(self):
        class TestingTemplate(MarkupTemplate):
            def mGreeting(self, name):
                return u'Hello %s!' % name
        code = '[Greeting name=[[name]]]'
        self.assertEqual(TestingTemplate().render(code), 'Hello [not found]!')

    def testContent(self):
        code = '[user.nickname]([user.age])'
        self.assertEqual(MarkupTemplate(user={'nickname': 'spide', 'age': 26}).render(code), 'spide(26)')

    def testComment(self):
        code = 'aaa[*comment[*]bbb'
        self.assertEqual(MarkupTemplate().render(code), 'aaabbb')

    def testEscaping(self):
        self.assertEqual(MarkupTemplate().render('[lt]1[gt]'), '[1]')


if __name__ == '__main__':
    unittest.main()


