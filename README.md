# CrackerJack Python

[![Python: 3.7](https://img.shields.io/badge/python-3.7%2B-blue)](https://docs.python.org/3/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![Code style: crackerjack](https://img.shields.io/badge/code%20style-crackerjack-000042)](https://github.com/lesleslie/crackerjack)


CrackerJack is a python coding, formatting, and documentation style for statically
 typed python >=3.7


### **Why CrackerJack?**

Crackerjack exists to make modern python code more elegant and readable. Let's face
 it, the python documentation system has been a major contributor to the languages
  popularity, but over time python code in packages and repositories has become so
   cluttered up with docstrings, doctests, and comments that it actually becomes
    really hard to find the actual code in it - nonetheless read through it. Yes, modern
     IDE's offer up options to fold the docstrings, but this doesn't help when
      looking through code on GitHub, or in an console based editor like vi and doesn't
       account for either for all the different ways that developers comment up their
        code. There must be some sanity!
        
Enter CrackerJack. CrackerJack works on the theory that with statically typed python
 code and explicit class, function, variable, and other object names the code should be
  straight forward to read and the documentation should pretty much be able to write
   itself (maybe with an ai down the road). CrackerJack also has a coding style whose
    guidelines exist to keep the codebase clean, elegant, standardized, and
     easily readable - give to me straight basically.
 
### **What doe this package do?**

Crackjack first cleans up the codebase by removing all docstrings and comments that
 do not conform to Crackerjack standards. The code is then reformatted to the
  [Black](https://github.com/ambv/black) code style, unused imports are removed, and 
  remaining imports sorted (via autoflake and reorder_python_imports). After that 
   [MonkeyType](https://monkeytype.readthedocs.io/en/stable/) is run to add type
    annotations to the code and optionally run through 
     [Mypy](https://mypy.readthedocs.io/en/latest/) to check for errors.
  
  CrackerJack will then install a documention loader to the modules \_\_doc\_\_
  attribute at the bottom, after all the functional code, which will dynamically
   generate the modules docstrings when called using the statically typed code, object
    names, and optional single-line docstrings (see guidelines below). 
    Additionally, the loader can append to or overwrite the current docstrings using an
     inline dictionary or an external source such as Markdown, YAML,
      pickled dictionaries, etc (of course you can just write your own
      dictionary for the \_\_doc\_\_ attribute as well and not use the loader
      ). Optionally, CrackerJack will generate and output the module docs, using 
        [pdoc](https://pdoc3.github.io/pdoc/), into HTML, PDF, or plain text.     
      
      
### **What are the rules?**
 (...more what you'd call "guidelines" than actual rules. \- Captain Barbossa )
 
 - Classes and functions need to be statically typed
 
 -
 
 - No spacing other than required by PEP 8 inside classes and function - should read
  like lines in a book
 
 - If a class can be a dataclass, it should be a dataclass
 
 - Use pathlib.Path not os.path. 
 
 - If a function of class is performing file operations it should be passed a Path
  object - not a string. 

 - Use of exec or exceptions for flow control - is not necessarily shunned upon if
  used in moderation but we do not promote them either.
  
 - Work in progress
 

