Simple markup langage for python

```python
import mrkev
code = '''
[Html :=[
    <html>[Header][Body]</html>
    ] Header=[
        <head><title>[title]</title></head>
    ] Body=[
        <body>[@]</body>
    ]
]
[Html [Hello world!]]
'''
print mrkev.Template(title=u'New Page').render(code)
```
is converted into
```html
<html><head><title>New page</title></head><body>Hello world!</body></html>
```

## Features
* runtime safe - templates cannot run own python code
* sandboxed function - template can be extended by new functions and syntax elements
* simple syntax - only two characters to escape

## Authors
* Frantisek Jahoda - implementation, some design choices - http://hradlo.blogspot.com/
* Tomas Novotny - original idea, syntax - http://extbrain.felk.cvut.cz/

