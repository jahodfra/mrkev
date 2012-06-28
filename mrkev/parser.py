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
        name = self.parseIdent()
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
                pname = self.parseParam()
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
                paramValue = self.parseContent()
                self.next()
                self.brackets -= 1
            else:
                #parameter value shortcut
                useName = self.parseParam()
                if not useName:
                    self.error(u'parameter "{0}" has no value'.format(pname))
                paramValue = [MarkupBlock(useName)]

            if pname == ':' and params:
                self.error('definition has to precede default parameters')

            if pname in params:
                self.error(u'parameter "{0}" has been already defined'.format(pname))

            params[pname] = paramValue
        return MarkupBlock(name, params)

    def parseIdent(self):
        return self.readUntil('[] \n\r\t')

    def parseParam(self):
        return self.readUntil('[] =\n\r\t')

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

    def readSpace(self):
        return self.read(lambda c: c.isspace())

