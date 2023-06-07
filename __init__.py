"""
Cythoner
--------

A python library that generates cython code automatically from a python file or code.
"""

import ast
from functools import wraps
from typing import Union

try:
    from Cython.Build import cythonize
    from distutils.core import setup
    CAN_CYTHONIZE = True
except ImportError:
    CAN_CYTHONIZE = False
    cythonize = None


operators = {
    ast.Add: '+',
    ast.Sub: '-',
    ast.Mult: '*',
    ast.Div: '/',
    ast.Pow: '**',
    ast.Mod: '%',
    ast.LShift: '<<',
    ast.RShift: '>>',
    ast.BitOr: '|',
    ast.BitXor: '^',
    ast.BitAnd: '&',
    ast.FloorDiv: '//',
    ast.Eq: '==',
    ast.NotEq: '!=',
    ast.Lt: '<',
    ast.LtE: '<=',
    ast.Gt: '>',
    ast.GtE: '>=',
    ast.Is: 'is',
    ast.IsNot: 'is not',
    ast.In: 'in',
    ast.NotIn: 'not in',
}


def space(n: int) -> str:
    """
    Return a string of n spaces

    :param n: the number of spaces
    :return: a string of n spaces
    """

    return ' ' * n


class Generator:
    def __init__(self, *, filename: str = None, code: str = None) -> None:
        """
        Generate a cython file or code from a python file or python code.

        :param filename: the path to the cython file
        :param code: the cython code to be converted
        :return: None, but the code is written into a file called generated.pyx
        """

        # Check if the filename or code is provided
        if filename is None and code is None:
            raise TypeError('filename or code must be specified')

        # Extract the code from the filename
        if filename is not None:
            with open(filename, 'r') as f:
                code = f.read()

        # Parse the code into python AST
        tree = ast.parse(code)
        generate = ''

        # Loop through the nodes
        for node in tree.body:
            generate += self.parse_stmt(node) + '\n'

        # Write the generated code into the generated.pyx file
        with open('generated.pyx', 'w') as f:
            f.write(generate)

    def parse_atom(self, node: Union[ast.Name, ast.Constant, ast.expr]) -> str:
        """
        Parse a literal into a string

        :param node: the literal node
        :return: the string representation of the literal
        """

        match type(node):
            case ast.Name:
                return str(node.id)
            case ast.Constant:
                return f'\'{node.value}\'' if isinstance(node.value, str) else str(node.value)
            case _:
                return self.parse_expr(node)

    def parse_stmt(self, stmt: ast.stmt) -> str:
        """
        Parse a statement into a string

        :param stmt: the statement node
        :return: the string representation of the statement
        """

        match type(stmt):
            case ast.Expr:
                return self.parse_expr(stmt)
            case ast.Pass:
                return f'{space(stmt.col_offset)}...'
            case ast.List:
                return f'{space(stmt.col_offset)}[{", ".join(map(self.parse_expr, stmt.elts))}]'
            case ast.AnnAssign:
                return f'{space(stmt.col_offset)}{stmt.target.id}: {stmt.annotation.id} = '\
                    f'{self.parse_expr(stmt.value)}'
            case ast.Assign:
                return f'{space(stmt.col_offset)}{stmt.targets[0].id} = {self.parse_expr(stmt.value)}'
            case ast.Return:
                return f'{space(stmt.col_offset)}return {self.parse_expr(stmt.value)}'
            case ast.For:
                return f'{space(stmt.col_offset)}for {stmt.target.id} in '\
                        f'{self.parse_expr(stmt.iter)}:\n{self.parse_body(stmt.body)}\n'
            case ast.AugAssign:
                return f'{space(stmt.col_offset)}{stmt.target} {operators[type(stmt.op)]}= '\
                    f'{self.parse_expr(stmt.value)}'
            case ast.If:
                return f'{space(stmt.col_offset)}if {self.parse_expr(stmt.test)}:\n'\
                    f'{self.parse_body(stmt.body)}\n'
            case ast.Import:
                return f'{space(stmt.col_offset)}import {self.parse_args(stmt.names)}'
            case ast.ImportFrom:
                if stmt.module is None:
                    return f'{space(stmt.col_offset)}from {"." * stmt.level} import '\
                            f'{", ".join(list(map(lambda x: x.name, stmt.names)))}\n'

                return f'{space(stmt.col_offset)}from {"." * stmt.level}{stmt.module} import '\
                    f'{", ".join(map(lambda x: x.name, stmt.names))}\n'
            case ast.Raise:
                if isinstance(stmt.exc, ast.Name):
                    return f'{space(stmt.col_offset)}raise {stmt.exc.id}'
                elif isinstance(stmt.exc, ast.Call):
                    return f'{space(stmt.col_offset)}raise {stmt.exc.func.id}('\
                            f'{self.parse_args(stmt.exc.args)}))'
            case ast.FunctionDef:
                options = []

                # Check for the no global interpreter lock (nogil) option
                for decorator in stmt.decorator_list:
                    if decorator.func.id == 'no_gil':
                        options.append('nogil')
                    elif decorator.func.id == 'except_error':
                        options.append('except ' + self.parse_args(decorator.args))

                if stmt.returns is not None:
                    return f'{space(stmt.col_offset)}cdef {stmt.returns.id} {stmt.name}'\
                        f'({self.parse_args(stmt.args)}) {", ".join(options)}:\n{self.parse_body(stmt.body)}\n'
                else:
                    return f'{space(stmt.col_offset)}def {stmt.name}({self.parse_args(stmt.args)}) '\
                            f'{", ".join(options)}:\n{self.parse_body(stmt.body)}\n'

    def parse_body(self, body: list[ast.stmt]) -> str:
        """
        Parse a function body into a string

        :param body: the body of the function as an ast node
        :return: the string representation of the body
        """

        r = ''
        for stmt in body:
            s = self.parse_stmt(stmt)
            if s is not None:
                r += s

        return r

    def parse_expr(self, expr: Union[ast.expr, ast.Expr, ast.stmt]) -> str:
        """
        Parse an expression into a string

        :param expr: the expression ast node
        :return: the string representation of the expression
        """

        if hasattr(expr, 'value'):
            match type(expr.value):
                case ast.Name:
                    return expr.id
                case ast.Call:
                    if isinstance(expr.value.func, ast.Attribute):
                        return f'{expr.value.func.value.id}.{expr.value.func.attr}'\
                            f'({self.parse_args(expr.value.args)})'
                            
                    return f'{expr.value.func.id}({self.parse_args(expr.value.args)})'
                case _:
                    return str(expr.value)
        elif isinstance(expr, ast.Call):
            if isinstance(expr.func, ast.Attribute):
                return f'{self.parse_atom(expr.func.value)}.{expr.func.attr}'\
                    f'({self.parse_args(expr.args)})'
            
            return f'{expr.func.id}({self.parse_args(expr.args)})'
        elif isinstance(expr, ast.BinOp):
            return f'{self.parse_atom(expr.left)} {operators[type(expr.op)]} {self.parse_atom(expr.right)}'
        elif isinstance(expr, ast.Compare):
            return f'{self.parse_atom(expr.left)} {operators[type(expr.ops)]} '\
                    f'{self.parse_atom(expr.comparators[0])}'
        else:
            return str(expr)

    def parse_args(self, arguments: Union[ast.arguments, list[ast.expr]]) -> str:
        """
        Parse arguments into a string

        :param arguments: the arguments ast node
        :return: the string representation of the arguments
        """

        r = ''
        if hasattr(arguments, 'args'):
            r += ', '.join([f'{arg.annotation.id} {arg.arg}' if arg.annotation else arg.arg
                            for arg in arguments.args])
        elif isinstance(arguments, list):
            r += ', '.join(list(map(self.parse_atom, arguments)))

        return r

    @staticmethod
    def make_module() -> None:
        """
        Create the .pyd file

        **This requires Cython to be installed
        Add the following to your command that you run the command with:
        build_ext --inplace**

        :return: None, but creates the .pyd file
        """

        if CAN_CYTHONIZE:
            setup(ext_modules=cythonize('generated.pyx', language_level='3'))
        else:
            raise ModuleNotFoundError('Cython not installed')


def except_error(err_name: str):
    """
    The function decorator for the except error option, used in cython.

    this is meant to be used like a decorator: @except_error( err )

    :param err_name: the name of the error
    :return: the decorator
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if e.__class__.__name__ != err_name:
                    raise e

        return wrapper

    return decorator

def no_gil():
    """
    The function decorator for the no global interpreter lock option, used in cython.

    this is meant to be used like a decorator: @no_gil()

    :return: the decorator
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


__all__ = [
    'Generator',
    'no_gil',
    'except_error'
]


if __name__ == '__main__':
    Generator(filename='test.py')
