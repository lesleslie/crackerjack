# Crackerjack Python

[![Python: 3.13](https://img.shields.io/badge/python-3.13%2B-blue)](https://docs.python.org/3/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![Checked with pyright](https://microsoft.github.io/pyright/img/pyright_badge.svg)](https://microsoft.github.io/pyright/)
[![pdm-managed](https://img.shields.io/badge/pdm-managed-blueviolet)](https://pdm.fming.dev)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![Code style: crackerjack](https://img.shields.io/badge/code%20style-crackerjack-000042)](https://github.com/lesleslie/crackerjack)

Crackerjack is a python coding style which uses a minimalist approach to produce elegant, easy to read, code.

crack·​er·​jack ˈkra-kər-ˌjak
: a person or thing of marked excellence

### **Why Crackerjack?**

Crackerjack works on the theory that with static typing and explicit class,
function, variable, and other object names - the code should be
straight forward to read. Documentation and tests should be able to write themselves using a generative ai.
Crackerjack provides a set of guidelines and utilities to keep the codebase clean, elegant, standardized, and
easily readable.

### **What does this package do?**

This package:

- streamlines and standardizes code style across numerous packages

- installs, or updates, a project's pre-commit tools as well as .gitignore & other config files
  to comply with evolving crackerjack standards

- runs the following pre-commit hooks (in order):
  * [pdm-lock-check](https://github.com/pdm-project/pdm)
  * various core [pre-commit-hooks](https://github.com/pre-commit/pre-commit-hooks)
  * [ruff](https://github.com/charliermarsh/ruff-pre-commit)
  * [vulture](https://github.com/jendrikseipp/vulture)
  * [creosote](https://github.com/fredrikaverpil/creosote)
  * [flynt](https://github.com/ikamensh/flynt/)
  * [codespell](https://github.com/codespell-project/codespell)
  * [autotyping](https://github.com/JelleZijlstra/autotyping)
  * [refurb](https://github.com/dosisod/refurb)
  * [bandit](https://github.com/PyCQA/bandit)
  * [pyright](https://github.com/RobertCraigie/pyright-python)
  * [ruff](https://github.com/charliermarsh/ruff-pre-commit) (again for sanity checking)

- converts/creates documentation in Markdown (md) (work in progress)

- runs tests and generates pytest mock stubs if needed (work in progress)

- bumps the project version and publishes it to PyPI

- commits changes to git repositories

### **What are the rules?**

(...more what you'd call "guidelines" than actual rules. -Captain Barbossa )

- code is statically typed

- all docstrings, README's, and other documentation is to be done in Markdown (md)

- use aiopath.AsyncPath or pathlib.Path not os.path

- import typing as t

- do not capitalize all letters in configuration settings or constants (we diverge from PEP-8 here
 for not other reason than it looks ugly)

- functions that deal with path operations should get passed AsyncPaths or Paths - not strings

- use PDM (uv support enabled) for dependency management and package building/publishing

- use pdoc and mkdocs for producing documentation

- use pytest for testing

- be compliant with, and only support, the latest python version within 2 months after release



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

For a full list of options:

```python -m crackerjack -h```

When you ready to publish your project:

``python -m crackerjack -p micro``

The -p option not only publishes your project but will bump your
project version for you. The options are 'micro', 'minor', and 'major'.
Put the -c option at the end and commit the bumped version to your git
repository at the same time:

``python -m crackerjack -p micro -c``

### **Contributing**

Crackerjack is currently an evolving standard. If you like the idea, but don't like certain things about it, or
would like new features added, let me know in Discussions, Issues, or email me.

### **License**

BSD-3-Clause
