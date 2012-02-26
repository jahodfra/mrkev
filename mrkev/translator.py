import re
from itertools import chain
from mrkev.parser import MarkupBlock

class UseBlock(object):
    __slots__ = ('name', 'default')
    def __init__(self, name, default=None):
        super(UseBlock, self).__init__()
        self.name = name
        self.default = default

    def __repr__(self):
        return '[%s|%s]' % (self.name, self.default)

class DefineBlock(object):
    __slots__ = ('_params', 'content')
    def __init__(self, content):
        super(DefineBlock, self).__init__()
        self.content = content
        self._params = {}

    def addParam(self, name, value, selfContainable=False):
        self._params[name] = value, selfContainable

    def get(self, name):
        v = self._params.get(name)
        return v[0] if v else None

    def isSelfContainable(self, name):
        v = self._params.get(name)
        return v[1] if v else None

    def __repr__(self):
        return '[def %s %s]' % (', '.join('%s=%s' % (p, v) for p, v in self._params.items()), self.content)

class Translator:
    def translate(self, blocks):
        if isinstance(blocks, list):
            isDefinition = lambda b: isinstance(b, MarkupBlock) and ':' in b.params
            definitions = [b for b in blocks if isDefinition(b)]
            usages = [b for b in blocks if not isDefinition(b)]
            content = self.translateContent(usages)
            if definitions:
                define = DefineBlock(content)
                for d in definitions:
                    define.addParam(d.name, self.translateDefinition(d), True)
                return define
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
            return replaceSpace(b)

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
                useBlock = UseBlock(b.name)
                if b.params:
                    item = DefineBlock(useBlock)
                    for p, value in b.params.items():
                        item.addParam(p, self.translate(value))
                else:
                    item = useBlock
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
                b.params['@'] = rest
                rest = []
                result.append(b)
            else:
                rest.append(b)
        result.reverse()
        rest.reverse()
        return rest + result

    def translateDefinition(self, block):
        content = self.translate(block.params[':'])
        if len(block.params) > 1:
            res = DefineBlock(content)
            for p, c in block.params.items():
                res.addParam(p, UseBlock(p, self.translate(c)))
        else:
            res = content
        return res

