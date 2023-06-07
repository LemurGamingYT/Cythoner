# Cythoner
 A converter for python to cython.

Cythoner is a program that converts python code to cython code to perform. Note that this is not really meant for use but a proof of concept, showing that it's possible to convert python code to cython with no effort.
Cythoner also converts annotations some annotations e.g. for parameters of user functions.

Cythoner is really really easy to break but some examples that work are:

*python*
```
def add(a: int, b: int) -> int:
    return a + b
```

*cython*
```
cdef int add(int a, int b) :
    return a + b
```

*python*
```
def test():
    for _ in range(100000):
        pass


test()
```

*cython*
```
def test() :
    for _ in range(100000):
        ...

test()
```
