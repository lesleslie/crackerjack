# Crackerjack Python

[![Python: 3.11](https://img.shields.io/badge/python-3.11%2B-blue)](https://docs.python.org/3/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![Checked with pyright](https://microsoft.github.io/pyright/img/pyright_badge.svg)](https://microsoft.github.io/pyright/)
[![pdm-managed](https://img.shields.io/badge/pdm-managed-blueviolet)](https://pdm.fming.dev)
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

### **Crackerjack philosophy...**

#### Virtual envs:

Let's face it virtual envs are a mess and a lot of time and resources are
spent maintaining them. [This](https://miro.medium.com/v2/resize:fit:984/format:webp/1*mHrDuetdLskvNHYucD9u3g.png) pretty
much says it all. Enough is enough.

#### Regression testing:

Again, here is what we believe become to be waste of time too. It takes more time to keep codebases compliant
with previous versions of python than it does to just update your code to run the latest versions of python
as they are released (within a liberal-ish timeline of course). Why are you running old versions of python anyway.
There are various easy ways to keep your system python versions up-to-date and
Docker containers for the latest versions are available immediately upon release. Most cloud providers
will support the new versions in their virtual machines and containers shortly after release as well. If your dependencies
break upon upgrade, file a bug report or fix it yourself. Simple enough.

#### ...the Crackerjack solution:

Crackerjack uses PDM with PEP-582 (yes, PEP-582 has been rejected but PDM still supports it and Crackerjack will continue to use it!).
No more virtualenvs. Update your system python versions as they are released and start
migrating your code. Crackerjack, and Crackerjack'd packages, should support the latest
python release's features within 2 month after the release and depend solely on that version. Again, if
something breaks, file a bug report or, even better, fix it yourself (maybe even learn something new things in the process).
Easy-peasy. You just saved yourself a zillion headaches and can sleep
better at night now.

### **What does this package do?**

This package:

- streamlines and standardizes code style across numerous packages

- installs, or updates, a project's pre-commit tools as well as .gitignore & other config files
  to comply with evolving crackerjack standards

- runs the following pre-commit hooks (in order):
  * various core pre-commit hooks
  * [black](https://github.com/ambv/black)
  * ruff
  * creosote
  * bandit
  * flynt
  * autotyping
  * refurb
  * pyright
  * ruff (again for sanity checking)
  * black (again for sanity checking)

- converts/creates documentation in Markdown (md) (work in progress)

- runs tests and generates pytest mock stubs if needed (work in progress)

- bumps the project version and publishes it to PyPI

- commits changes to git repositories

### **What are the rules?**

(...more what you'd call "guidelines" than actual rules. -Captain Barbossa )

- code is statically typed

- all docstrings, README's, and other documentation is to be done in Markdown (md)

- format with black

- use aiopath.AsyncPath or pathlib.Path not os.path

- import typing as t

- do not capitalize all letters in configuration settings or constants (we diverge from PEP-8 here
 for not other reason than it looks ugly)

- functions that deal with path operations should get passed AsyncPaths or Paths - not strings

- if a class can be a dataclasses.dataclass, pydantic.BaseModel, or msgspec.Struct it should be

- force single line imports (will support isort Vertical Hanging Indent when ruff does)

- use PDM and PEP-582 for dependency management and package building/publishing

- use pdoc and mkdocs for producing documentation

- use pytest for testing

- be compliant with the latest python version within 2 months after release



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
repository at the same time.

### **Contributing**

Crackerjack is currently an evolving standard. If you like the idea, but don't like certain things about it, or
would like new features added, let me know in Discussions, Issues, or email me.

### **License**

BSD-3-Clause
