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

    def testAttributeNameWithLineEnd(self):
        self.assertRaises(MarkupSyntaxError, lambda: parse('[t a\n]'))

    def testTagNameWithLineEnd(self):
        self.assertEqual(parse('[t\n]'), [use('t')])

    def testTagNameContainingSpecialCharacters(self):
        self.assertEqual(parse('["$#%!=]'), [use('"$#%!=')])

    def testPreserveLineEnds(self):
        text = '\r\n\na\nb'
        self.assertEqual(parse(text), [text])

