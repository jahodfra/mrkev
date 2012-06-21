from mrkev.parser import MarkupBlock

class BaseContext(object):
    __slots__ = ('params',)
    def __init__(self):
        self.params = {}

    def addParam(self, name, value):
        self.params[name] = value

    def get(self, name):
        return self.params.get(name)


class CallBlock(BaseContext):
    __slots__ = ('name', )
    def __init__(self, name):
        super(CallBlock, self).__init__()
        self.name = name

    def __repr__(self):
        return '[call %s]' % (self.name,)


class CallParameter(object):
    __slots__ = ('name', 'lexicalScope', 'inDefaultParameter')
    def __init__(self, name, lexicalScope, inDefaultParameter):
        super(CallParameter, self).__init__()
        self.name = name
        self.lexicalScope = lexicalScope
        self.inDefaultParameter = inDefaultParameter

    def __repr__(self):
        return '[param %s]' % (self.name,)


class BlockDefinition(BaseContext):
    __slots__ = ('name', 'params', 'content')
    def __init__(self, name):
        super(BlockDefinition, self).__init__()
        self.name = name
        self.content = []

    def __repr__(self):
        return '[def %s %s]' % (', '.join('%s=%s' % (p, v) for p, v in self.params.items()), self.content)


class BlockScope(BaseContext):
    __slots__ = ('params', 'content')
    def __init__(self):
        super(BlockScope, self).__init__()

    def __repr__(self):
        return '[scope %s %s]' % (', '.join('%s=%s' % (p, v) for p, v in self.params.items()), self.content)


class Translator:
    def __init__(self):
        self.lexicalScope = []
        self.parameterName = []
        self.inDefaultParameter = []

    def translate(self, blocks):
        self.lexicalScope.append(None)
        self.parameterName.append('')
        self.inDefaultParameter.append(False)
        res = self.translateContent(blocks)
        self.lexicalScope.pop()
        self.parameterName.pop()
        self.inDefaultParameter.pop()
        return res

    def translateContent(self, blocks):
        if isinstance(blocks, list):
            isDefinition = lambda b: isinstance(b, MarkupBlock) and ':' in b.params
            definitions = [b for b in blocks if isDefinition(b)]
            usages = [b for b in blocks if not isDefinition(b)]
            content = self.translatePlainContent(usages)
            if definitions:
                define = BlockScope()
                define.content = content
                self.parameterName.append('')
                for d in definitions:
                    define.addParam(d.name, self.translateDefinition(d))
                self.parameterName.pop()
                return define
            else:
                return content
        else:
            raise AttributeError('blocks = %s' % blocks)

    def translatePlainContent(self, blocks):
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
            return b

        seq = []
        if any(isinstance(b, MarkupBlock) and b.name == '.' for b in blocks):
            blocks = self.translateList(blocks)
        for b in blocks:
            if isinstance(b, basestring):
                item = stripString(b, not seq, seq[-1] if seq and isinstance(seq[-1], basestring) else None)
                if item is None:
                    continue
            else:
                if b.name.startswith('>'):
                    self.translateLink(b)
                if b.name == '@':
                    #translate alias
                    if self.parameterName[-1]:
                        b.name = self.parameterName[-1]
                if b.name[0] == '#':
                    item = CallParameter(b.name, lexicalScope=self.lexicalScope[-1], inDefaultParameter=self.inDefaultParameter[-1])
                else:
                    item = CallBlock(b.name)
                    for p, value in b.params.items():
                        pname = formParameterName(p)
                        self.parameterName.append(pname)
                        item.addParam(pname, self.translateContent(value))
                        self.parameterName.pop()
            seq.append(item)
        if seq and isinstance(seq[-1], basestring):
            s = seq[-1].rstrip()
            if not s:
                seq.pop()
            else:
                seq[-1] = s
        if len(seq) == 1:
            return seq[0]
        else:
            return [seq]

    def translateLink(self, block):
        if len(block.name) > 1:
            block.params['Target'] = [block.name[1:]]
        block.name = 'Link'

    def translateList(self, blocks):
        rest = []
        result = []
        for b in reversed(blocks):
            if isinstance(b, MarkupBlock) and b.name == '.':
                b.name = 'Item'
                rest.reverse()
                b.params['#'] = rest
                rest = []
                result.append(b)
            else:
                rest.append(b)
        result.reverse()
        rest.reverse()
        return rest + result

    def translateDefinition(self, block):
        res = BlockDefinition(block.name)
        self.lexicalScope.append(res)
        self.parameterName.append('')
        res.content = self.translateContent(block.params[':'])
        self.parameterName.pop()
        for p, c in block.params.items():
            if p != ':':
                pname = formParameterName(p)
                self.parameterName.append(pname)
                self.inDefaultParameter.append(True)
                res.addParam(pname, self.translateContent(c))
                self.parameterName.pop()
                self.inDefaultParameter.pop()
        self.lexicalScope.pop()
        return res

def formParameterName(param):
    if param != '#':
        param = '#' + param
    return param

