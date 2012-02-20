#encoding: utf-8

import unittest
from mrkev.interpreter import Template

class TestInterpretation(unittest.TestCase):
    def testPlaceVariable(self):
        self.assertEqual(Template('Hello [#name]!').render(name='world'), 'Hello world!')

    def testCallFunction(self):
        class TestingTemplate(Template):
            def mGreeting(self, name):
                return u'Hello %s!' % name
        self.assertEqual(TestingTemplate('Mr. White: [Greeting name=[Ms. Black]]').render(), 'Mr. White: Hello Ms. Black!')

    def testList(self):
        code = '''
        <ul>[List Seq=[[#Literature]] [
            <li[*just an example better use css selector*][If [[$Last]] Then=[[Sp]class="last"]]>[$Order]. [$Item]</li>
        ]]</ul>
        '''
        self.assertEqual(Template(code).render(Literature=[u'Shakespear', u'Čapek']), u'<ul><li>1. Shakespear</li><li class="last">2. Čapek</li></ul>')

    def testDefineTemplate(self):
        code = '''
        [Html :=[
            <html>[Header][Body]</html>
            ] Header=[
                <head><title>[Title]</title></head>
            ] Body=[
                <body>[@]</body>
            ]
        ]
        [Html Title=[New page] [Hello world!]]
        '''
        self.assertEqual(Template(code).render(), '<html><head><title>New page</title></head><body>Hello world!</body></html>')

    def testNotFound(self):
        code = '[a] [b c=[d]]'
        self.assertEqual(Template(code).render(), '[a not found] [b not found]')

    def testRecursion(self):
        code = '''
        [Greeting:=[Hello [name]!]]
        [Greeting name=[[name]]]
        '''
        self.assertEqual(Template(code).render(), 'Hello [name not found]!')

    def testRecursion2(self):
        #note that same definition c is used multiple times while evaluating itself
        #see selfContainable property
        code = '''
        [c:=[[@]]]
        [c name=[a] [
            [c name=[[name]b] [
                [c name=[[name]c] [
                    Hello [name]!
                ]]
            ]]
        ]]
        '''
        self.assertEqual(Template(code).render(), 'Hello abc!')

    def testRecursion3(self):
        #selfContainable property enables infinite recursion, this test ensures, that program has some limit on it
        code = '[c:=[[c]]][c]'
        self.assertEqual(Template(code).render(), '[recurrence limit for c]')

    def testContent(self):
        code = '[#user.nickname]([#user.age])'
        self.assertEqual(Template(code).render(user={'nickname': 'spide', 'age': 26}), 'spide(26)')

    def testComment(self):
        code = 'aaa[*comment[*]bbb'
        self.assertEqual(Template(code).render(), 'aaabbb')

    def testEscaping(self):
        self.assertEqual(Template('[(]1[)]').render(), '[1]')

