import unittest
from mrkev.parser import Parser, MarkupBlock, MarkupSyntaxError

def parse(s):
    return Parser(s).parse()

class TestParsing(unittest.TestCase):
    def testParse(self):
        use = MarkupBlock
        parseTree = [use('import', {'@': ['guideline']})]
        self.assertEqual(parse('[import [guideline]]'), parseTree)

        parseTree = [use('for', {
            'list': [use('enumerate', {'list': [use('customers')]})],
            'template': [use('order'), '. ', use('name')]
        })]
        self.assertEqual(parse('''[for list=[[enumerate list=[[customers]]]] template=[[order]. [name]]]'''), parseTree)
        self.assertRaises(MarkupSyntaxError, lambda: parse('[a x= []]'))

