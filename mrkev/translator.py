from mrkev.parser import MarkupBlock

class BaseContext(object):
    __slots__ = ('params', 'useParams')
    def __init__(self):
        self.params = {}
        self.useParams = {}

    def addParam(self, name, value):
        self.params[name] = value

    def get(self, name):
        return self.useParams.get(name) or self.params.get(name)


class CallBlock(BaseContext):
    __slots__ = ('name', )
    def __init__(self, name):
        super(CallBlock, self).__init__()
        self.name = name

    def __repr__(self):
        return '[call %s]' % (self.name,)


class CallParameter(object):
    __slots__ = ('name', 'lexicalScope')
    def __init__(self, name, lexicalScope):
        super(CallParameter, self).__init__()
        self.name = name
        self.lexicalScope = lexicalScope

    def __repr__(self):
        return '[param %s]' % (self.name,)


class DefineBlock(BaseContext):
    __slots__ = ('params', 'content')
    def __init__(self):
        super(DefineBlock, self).__init__()

    def __repr__(self):
        return '[def %s %s]' % (', '.join('%s=%s' % (p, v) for p, v in self._params.items()), self.content)


class Translator:
    def translate(self, blocks):
        return self.translateContent(blocks, lexicalScope=None, parameterName='')

    def translateContent(self, blocks, lexicalScope, parameterName):
        if isinstance(blocks, list):
            isDefinition = lambda b: isinstance(b, MarkupBlock) and ':' in b.params
            definitions = [b for b in blocks if isDefinition(b)]
            usages = [b for b in blocks if not isDefinition(b)]
            content = self.translatePlainContent(usages, lexicalScope=lexicalScope, parameterName=parameterName)
            if definitions:
                define = DefineBlock()
                define.content = content
                for d in definitions:
                    define.addParam(d.name, self.translateDefinition(d, lexicalScope=lexicalScope))
                return define
            else:
                return content
        else:
            raise AttributeError('blocks = %s' % blocks)

    def translatePlainContent(self, blocks, lexicalScope, parameterName):
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
                    if parameterName:
                        b.name = parameterName
                if b.name[0] == '#':
                    item = CallParameter(b.name, lexicalScope=lexicalScope)
                else:
                    item = CallBlock(b.name)
                    for p, value in b.params.items():
                        pname = formParameterName(p)
                        item.addParam(pname, self.translateContent(value, lexicalScope=lexicalScope, parameterName=pname))
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

    def translateDefinition(self, block, lexicalScope):
        res = DefineBlock()
        res.content = self.translateContent(block.params[':'], lexicalScope=res, parameterName='')
        for p, c in block.params.items():
            if p != ':':
                pname = formParameterName(p)
                res.addParam(pname, self.translateContent(c, lexicalScope=res, parameterName=pname))
        return res

def formParameterName(param):
    if param != '#':
        param = '#' + param
    return param

