import unittest
from mrkev.parser import Parser, MarkupBlock as use, MarkupSyntaxError

def parse(s):
    return Parser(s).parse()

class TestParsing(unittest.TestCase):
    def testSimpleUsage(self):
        parseTree = [use('import', {'#': ['guideline']})]
        self.assertEqual(parse('[import [guideline]]'), parseTree)

    def testListTemplate(self):
        parseTree = [use('for', {
            'list': [use('enumerate', {'list': [use('customers')]})],
            'template': [use('order'), '. ', use('name')]
        })]
        self.assertEqual(parse('[for list=[[enumerate list=[[customers]]]] template=[[order]. [name]]]'), parseTree)

    def testSpaceAfterEqualSign(self):
        self.assertRaises(MarkupSyntaxError, lambda: parse('[a x= []]'))

    def testMismatchingBrackets(self):
        self.assertRaises(MarkupSyntaxError, lambda: parse('[a]]'))

    def testMisingCloseBracket(self):
        self.assertRaises(MarkupSyntaxError, lambda: parse('[a'))

    def testNoName(self):
        self.assertRaises(MarkupSyntaxError, lambda: parse('[]'))

    def testAttributeName(self):
        self.assertEqual(parse('[t "$#:%!=[]]'), [use('t', {'"$#:%!': []})])

    def testTagNameWithLineEnd(self):
        self.assertEqual(parse('[t\n]'), [use('t')])

    def testTagNameContainingSpecialCharacters(self):
        self.assertEqual(parse('["$#%!=]'), [use('"$#%!=')])

    def testPreserveLineEnds(self):
        text = '\r\n\na\nb'
        self.assertEqual(parse(text), [text])

    def testContentShortcut(self):
        self.assertEqual(parse('[a #b]'), [use('a', {'#': [use('#b')]})])

    def testAtributeShortcut(self):
        self.assertEqual(parse('[a b=c]'), [use('a', {'b': [use('c')]})])

    def testDefinitionShortcut(self):
        a = parse('[a :=b]')
        b = parse('[a :=[[b]]]')
        self.assertEqual(a, b)
        self.assertEqual(a, [use('a', {':': [use('b')]})])

    def testDefinitionAfterParameter(self):
        self.assertRaises(MarkupSyntaxError, lambda: parse('[a b=[] :=[]]'))

    def testParameterDeclaredTwice(self):
        self.assertRaises(MarkupSyntaxError, lambda: parse('[a b=[] b=[]]'))

