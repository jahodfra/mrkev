import re
from itertools import chain
from mrkev.parser import MarkupBlock

class BaseValue(object):
    pass

class StringValue(BaseValue):
    __slots__ = ('s',)
    def __init__(self, s):
        super(StringValue, self).__init__()
        self.s = s

    def __repr__(self):
        return '"%s"' % self.s

class BlockCollection(BaseValue):
    __slots__ = ('blocks',)
    def __init__(self, blocks):
        super(BlockCollection, self).__init__()
        self.blocks = blocks

    def __repr__(self):
        return '[%s]' % ', '.join(repr(b) for b in self.blocks)

class UseBlock(BaseValue):
    __slots__ = ('name', 'default', 'selfContainable')
    def __init__(self, name, default=None):
        super(UseBlock, self).__init__()
        self.name = name
        self.default = default

    def __repr__(self):
        return '[%s|%s]' % (self.name, self.default)

class DefineBlock(BaseValue):
    __slots__ = ('params', 'content')
    def __init__(self, params, content):
        super(DefineBlock, self).__init__()
        self.params = params
        self.content = content

    def __repr__(self):
        return '[def %s %s]' % (', '.join('%s=%s' % (p, v) for p, v in self.params.items()), self.content)

class Translator:
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
        if any(isinstance(b, MarkupBlock) and b.name == '.' for b in blocks):
            blocks = self.translateList(blocks)
        for b in blocks:
            if isinstance(b, basestring):
                item = stripString(b, not seq, seq[-1].s if seq and isinstance(seq[-1], StringValue) else None)
                if item is None:
                    continue
            else:
                if b.name.startswith('>'):
                    self.translateLink(b)
                useBlock = UseBlock(b.name)
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

    def translateLink(self, block):
        block.params['Target'] = [block.name[1:]]
        block.name = '>'


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
            res = DefineBlock(dict((p, UseBlock(p, self.translate(c))) for p, c in block.params.items()), content)
        else:
            res = content
        res.selfContainable = True
        return res

