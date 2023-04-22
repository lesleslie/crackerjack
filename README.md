# Crackerjack Python

[![Python: 3.7](https://img.shields.io/badge/python-3.11%2B-blue)](https://docs.python.org/3/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![Code style: crackerjack](https://img.shields.io/badge/code%20style-crackerjack-000042)](https://github.com/lesleslie/crackerjack)

Crackerjack is a python coding style which uses a minimalist approach to produce elegant, easy to read, code.

### **Why Crackerjack?**

Let's face it, the python documentation system has been a major contributor to the
languages popularity, but over time python code in packages and repositories has
become so cluttered up with docstrings, doctests, and comments that it actually
becomes really hard to find the actual code in it - nonetheless read through it.
Yes, modern IDE's offer up options to fold the docstrings, but this doesn't help
when looking through code on GitHub, or in an console based editor like vi and
doesn't account for either for all the different ways that developers comment
up their code. There must be some sanity!

Enter Crackerjack. Crackerjack works on the theory that with static typing and explicit classes,
functions, variables, and other object names - the code should be
straight forward to read and the documentation should pretty much be able to write
itself. Crackerjack provides a set of guidelines and utilities to keep the codebase clean, elegant, standardized, and
easily readable - give it to me straight basically.

### **What does this package do?**

This package:

- removes all docstrings and comments that
  do not conform to Crackerjack standards (see below)

- identifies and removes unused dependencies with deptry

- reformats the code with [Black](https://github.com/ambv/black)

- uses [MonkeyType](https://monkeytype.readthedocs.io/en/stable/) to add missing type
  annotations to the code

- does import sorting, type checking, complexity analysis, with ruff

- streamlines code with refurb

- converts all documentation to Markdown (md)

- removes pipenv, poetry, and hatch build, dependency management, and virtual environment
  management packages and replace them with PDM using PEP 582 (keep it simple stupid)

- generates pytest mock stubs if needed

### **What are the rules?**

(...more what you'd call "guidelines" than actual rules. -Captain Barbossa )

- all docstrings, README's, and other documentation is to be done in Markdown (md)

- format with black

- use pathlib.Path - not os.path

- use dataclasses or pydantic models whenever possible

- sort imports in the style of isort multi-line-output 3 (Vertical Hanging Indent)

- use PDM and PEP 582 for dependency management and package building/publishing

- use pydoc and mkdocs for producing documentation

- use pytest for testing

- docstrings can only be one line

- non-inline comments are to be single-line and in between code as
  long as they are only a few words long and seperated by two blank lines at the top
  and at 1-2 blank lines below

- code is statically typed

- variable docstrings are supported as outlined in
  [PEP-224](https://www.python.org/dev/peps/pep-0224/) as well as the module-level
  __pdoc__ dictionary (see [pdoc docs](
  https://pdoc3.github.io/pdoc/doc/pdoc/#overriding-docstrings-with-__pdoc__))

- do not use exec (there is always another way)


- 



