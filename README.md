# Crackerjack Python

[![Python: 3.7](https://img.shields.io/badge/python-3.11%2B-blue)](https://docs.python.org/3/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![Code style: crackerjack](https://img.shields.io/badge/code%20style-crackerjack-000042)](https://github.com/lesleslie/crackerjack)

Crackerjack is a python coding style which uses a minimalist approach to produce elegant, easy to read, code.

### **Why Crackerjack?**

Crackerjack works on the theory that with static typing and explicit classes,
functions, variables, and other object names - the code should be
straight forward to read and the documentation should pretty much be able to write
itself. Crackerjack provides a set of guidelines and utilities to keep the codebase clean, elegant, standardized, and
easily readable.

### **What does this package do?**

This package:

- identifies and removes unused dependencies with creosote

- reformats the code with [Black](https://github.com/ambv/black)

- uses autotype to add missing type annotations to the code

- does import sorting, linting, and complexity analysis with ruff

- uses mypy for type checking

- streamlines code with refurb

- converts/creates documentation in Markdown (md)

- installs, or updates, a projects pre-commit tools and gitignore
  to comply with evolving crackerjack standards

- removes pipenv, poetry, and hatch build, dependency management, and virtual environment
  management packages and replace them with PDM using PEP 582

- generates pytest mock stubs if needed

### **What are the rules?**

(...more what you'd call "guidelines" than actual rules. -Captain Barbossa )

- all docstrings, README's, and other documentation is to be done in Markdown (md)

- format with black

- use pathlib.Path - not os.path

- use dataclasses or pydantic models whenever possible

- force single line imports

- use PDM and PEP 582 for dependency management and package building/publishing

- use pdoc and mkdocs for producing documentation

- use pytest for testing

- code is statically typed

[//]: # (- variable docstrings are supported as outlined in)

[//]: # (  [PEP-224]&#40;https://www.python.org/dev/peps/pep-0224/&#41; as well as the module-level)

[//]: # (  __pdoc__ dictionary &#40;see [pdoc docs]&#40;)

[//]: # (  https://pdoc3.github.io/pdoc/doc/pdoc/#overriding-docstrings-with-__pdoc__&#41;&#41;)


### **Installation**

From your projects root directory:

```pdm add -d crackerjack```

### **Usage**

From your projects root directory:

```python -m crackerjack```

Cracker jack will take care of the rest.

When you ready to publish your project:

``python -m crackerjack -p micro``

The -p option not only publishes your project but will bump your
project version for you. The options are 'micro', 'minor', and 'major'.
