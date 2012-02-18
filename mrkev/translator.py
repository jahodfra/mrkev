import re
from itertools import chain
from mrkev.parser import MarkupBlock

MISSING_MSG = '[%s not found]'

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
        for b in blocks:
            if isinstance(b, basestring):
                item = stripString(b, not seq, seq[-1].s if seq and isinstance(seq[-1], StringValue) else None)
                if item is None:
                    continue
            else:
                useBlock = UseBlock(b.name, StringValue(MISSING_MSG % b.name))
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

