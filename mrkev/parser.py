import re
from StringIO import StringIO

class MarkupBlock(object):
    def __init__(self, name, params=None):
        self.name = name
        self.params = params or {}

    def __eq__(self, o):
        return isinstance(o, MarkupBlock) and self.name == o.name and self.params == o.params

    def __repr__(self):
        params = u', '.join('{0}={1}'.format(k, v) for k, v in self.params.items())
        return u'{0}({1})'.format(self.name, params)

class MarkupSyntaxError(Exception):
    def __init__(self, msg, inputFile):
        Exception.__init__(self, msg)
        self.msg = msg
        self.inputFile = inputFile

    def __str__(self):
        return '%s\n  File "%s", line %d\n    %s\n    %s' % (self.msg, self.inputFile.name, self.inputFile.lineno + 1, self.inputFile.line, ' '*self.inputFile.pos + '^')

class InputFile:
    def __init__(self, text, name):
        self.fin = StringIO(text)
        self.name = name
        self.pos = 0
        self.line = ''
        self.lineno = 0

    def __iter__(self):
        for lineno, line in enumerate(self.fin):
            self.lineno = lineno
            self.line = line
            for pos, char in enumerate(line):
                self.pos = pos
                yield char
        while True:
            yield Parser.EOF

class Parser:
    ''' Grammar:

        FILE = CONTENT
        CONTENT = [STR | BLOCK]*
        BLOCK = '[', INDENT, [PARAMS]*, ']'
        PARAMS = IDENT, '=[', CONTENT, ']'
            | '=[', CONTENT, ']'
    '''
    RE_IDENT = re.compile(r'[^\[\] \:\n\r\t]')
    RE_PARAM = re.compile(r'[^\[\] \=\n\r\t]')

    class EndOfLineType:
        def __str__(self):
            return 'end of line'

    EOF = EndOfLineType()

    def __init__(self, content, filename='<stdin>'):
        content = InputFile(content, filename)
        self.content = content
        self.inputStream = iter(content)
        self.brackets = 0
        self.currentChar = self.inputStream.next()

    def parse(self):
        self.brackets = 0
        return self.parseContent()

    def error(self, msg):
        raise MarkupSyntaxError(msg, self.content)

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
        name = self.readWhileRe(self.RE_IDENT)
        if not name:
            self.error('no name')
        params = {}
        while True:
            self.readSpace()
            pname = '#'
            current = self.getCurrent()
            if current == ']':
                self.next()
                break
            elif current != '[':
                pname = self.readWhileRe(self.RE_PARAM)
                current = self.getCurrent()
                if current == '=':
                    self.next()
                elif current != self.EOF and pname:
                    #content shortcut
                    params['#'] = [MarkupBlock(pname)]
                    continue

            if self.getCurrent() == '[':
                self.brackets += 1
                self.next()
                params[pname] = self.parseContent()
                self.next()
                self.brackets -= 1
            else:
                #parameter value shortcut
                useName = self.readWhileRe(self.RE_PARAM)
                if not useName:
                    self.error('parameter "{0}" has no value'.format(pname))
                params[pname] = [MarkupBlock(useName)]
        return MarkupBlock(name, params)

    def check(self, char):
        if self.getCurrent() != char:
            self.error('expects char "%s" found "%s"' % (char, self.getCurrent()))

    def getCurrent(self):
        return self.currentChar

    def next(self):
        if self.currentChar != self.EOF:
            self.currentChar = self.inputStream.next()

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

    def readWhileRe(self, regex):
        return self.read(regex.match)

    def readSpace(self):
        return self.read(lambda c: c.isspace())

