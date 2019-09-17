# CrackerJack Python

[![Python: 3.7](https://img.shields.io/badge/python-3.7%2B-blue)](https://docs.python.org/3/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![Code style: crackerjack](https://img.shields.io/badge/code%20style-crackerjack-000042)](https://github.com/lesleslie/crackerjack)


CrackerJack is a python coding, formatting, and documentation style for statically
 typed python >=3.7


### **Why CrackerJack?**

Crackerjack (PEP 8000) exists to make modern python code more elegant and readable.
 Let's face it, the python documentation system has been a major contributor to the
  languages popularity, but over time python code in packages and repositories has
   become so cluttered up with docstrings, doctests, and comments that it actually
    becomes really hard to find the actual code in it - nonetheless read through it.
     Yes, modern IDE's offer up options to fold the docstrings, but this doesn't help
      when looking through code on GitHub, or in an console based editor like vi and
       doesn't account for either for all the different ways that developers comment
        up their code. There must be some sanity!
        
Enter CrackerJack. CrackerJack works on the theory that with statically typed python
 code and explicit class, function, variable, and other object names the code should be
  straight forward to read and the documentation should pretty much be able to write
   itself (can you say ai). CrackerJack also has coding style
    guidelines that exist to keep the codebase clean, elegant, standardized, and
     easily readable - give to me straight basically.
 
### **What doe this package do?**

Crackjack first cleans up the codebase by removing all docstrings and comments that
 do not conform to Crackerjack standards (see below). The code is then reformatted to
  the [Black](https://github.com/ambv/black) code style, unused imports are removed
   with [autoflake](https://github.com/myint/autoflake), and remaining imports sorted
    by [reorder_python_imports](https://github.com/asottile/reorder_python_imports).
    After that 
   [MonkeyType](https://monkeytype.readthedocs.io/en/stable/) is run to add type
    annotations to the code and optionally run through 
     [Mypy](https://mypy.readthedocs.io/en/latest/) to check for errors.
        Optionally, CrackerJack will generate and output the module docs, using 
         [pdoc](https://pdoc3.github.io/pdoc/), into HTML, PDF, or plain text.
         Eventually the option for ai generated docs using the statically typed code,
         variable/class/function names, and docstings will be available.    
      
      
### **What are the rules?**
 (...more what you'd call "guidelines" than actual rules. \- Captain Barbossa )
 
 - All docstrings, README's, and other documentation is to be done in Markdown (md) 
 
 - Docstrings can only be one line. Variable docstrings are supported as outlined in 
 [PEP-224](https://www.python.org/dev/peps/pep-0224/) as well as the module-level
  __pdoc__ dictionary (see [pdoc docs](
  https://pdoc3.github.io/pdoc/doc/pdoc/#overriding-docstrings-with-__pdoc__))
 
 - Inline comments are supported as are single-line line comments in between code as
  long as they are only a few words long and seperated by two blank lines at the top
   and at 1-2 blank line below.
 
 - Classes and functions need to be statically typed
 
 - Code needs to be [black](https://github.com/ambv/black)'ed
 
 - Imports are one single import per line
  (see [reorder_python_imports](https://github.com/asottile/reorder_python_imports
  )) - this not only helps aviod merge conflicts but makes it easier to manipulate if
   using hot-keys
 
 - If a class can be a dataclass, it should be a dataclass
 
 - Use pathlib.Path not os.path.
 
 - If a function or class is performing file operations it should be passed a Path
  object - not a string. 

 - Use of exec, or exceptions for flow control, is not necessarily shunned upon if
  used in moderation but we do not promote their use either
  
 - Work in progress
 

