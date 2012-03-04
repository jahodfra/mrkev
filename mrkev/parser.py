import re

'''
Grammar:
    FILE = CONTENT
    CONTENT = [STR | BLOCK]*
    BLOCK = '[', INDENT, [PARAMS]*, ']'
    PARAMS = IDENT, '=[', CONTENT, ']'
           | '=[', CONTENT, ']'
'''

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
    RE_IDENT = re.compile(r'[^\[\] \:\n\r\t]')
    RE_PARAM = re.compile(r'[^\[\] \=\n\r\t]')

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
        name = self.readWhileRe(self.RE_IDENT)
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

