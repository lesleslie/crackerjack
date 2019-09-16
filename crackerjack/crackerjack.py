from collections import namedtuple
from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
from inspect import (
    cleandoc,
    currentframe,
    getdoc,
    getfile,
    getmembers,
    isclass,
    isfunction,
)
from os import getcwd, path as op
from pathlib import Path
from subprocess import call

from black import InvalidInput, format_str
from blib2to3.pgen2.tokenize import TokenError
from click import command, help_option, option
from pipreqs.pipreqs import get_all_imports
from .utils import pprint

for m in [pprint]:
    pass

pager_delay = 0.2

basedir = op.abspath(getcwd())

our_path = getfile(currentframe())
our_parent = Path(our_path).resolve().parent
our_imports = get_all_imports(our_parent)


docs = list()
comments = list()


def process_doc(doc):
    for l in [l.strip() for l in doc.splitlines() if not l.strip() in docs]:
        docs.append(l)


def process_obj(obj):
    doc = getdoc(obj[1])
    if doc:
        print(f"Removing doc string from:  {obj[0]}")
        process_doc(doc)


def get_doc(obj):
    process_obj(obj)
    functions = getmembers(obj[1], isfunction)
    for obj2 in functions:
        process_obj(obj2)
        objs = getmembers(obj2[1], isfunction)
        for obj3 in objs:
            process_obj(obj3)


def process_text(text):
    resp = namedtuple("FormatResponse", ["input", "output", "error", "success"])
    resp.input = text
    resp.output = text
    resp.success = False
    resp.err = None
    try:
        text = cleandoc(text)
        resp.output = format_str(text, line_length=88)
        resp.success = True
    except InvalidInput as err:
        resp.error = err
        print(f"!!! InvalidInput  -  {err}")
    except TokenError as err:
        resp.error = err
        print(f"!!! TokenError  -  {err}")
    finally:
        resp.output = cleandoc(text)
        return resp


def install(package):
    try:
        import_module(package)
    except ImportError:
        print("Installing: ", package)
        call(["pip", "install", package, "--disable-pip-version-check"])
    finally:
        globals()[package] = import_module(package)


def uninstall(package):
    if (package == "pip") or (package in our_imports):
        return False
    print("Uninstalling: ", package)
    call(["pip", "uninstall", package, "-y"])
    return True


def crackerjack_it(fn, exclude=False, interactive=False, dry_run=False, verbose=False):
    print("\nCrackerJacking...\n")

    module_name = fn.rstrip(".py")

    fn = op.join(op.abspath(getcwd()), fn)
    module_imports = get_all_imports(getcwd())

    for m in module_imports:
        install(m)

    with open(fn, "r") as f:
        text = f.read()
        f.close()

    print("\nPre-processing text.....\n\n")
    pre = process_text(text)
    text = pre.output

    spec = spec_from_file_location(module_name, op.join(basedir, fn))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    functions = getmembers(module, isfunction)
    classes = getmembers(module, isclass)

    for obj in classes + functions:
        get_doc(obj)

    for line in docs:
        text = text.replace(line, "")

    if not exclude:
        print("\nRemoving remaining docstrings, comments, and blank " "lines.....\n\n")
        lines = list()
        del_lines = False
        for line in text.splitlines(True):
            print(line)
            if len(line) < 2:
                print(1)
                continue
            elif '"""' in line:
                print(2)
                del_lines = not del_lines
                continue
            elif del_lines:
                print(3)
                continue
            elif line.lstrip().startswith("#"):
                print(4)
                continue
            lines.append(line)

        text = "".join(lines)

    print("\n\nPost-processing text.....\n\n")
    post = process_text(text)

    if post.success:
        print(post.output)
        print("\n\n\t*** Success! ***\n\n")

        if not dry_run:
            with open(fn, "r+") as f:
                f.seek(0)
                f.truncate()
                f.write(post.output)
                f.close()
    elif post.error:
        print(f"Error formatting: {post.error}\n\n")

    for m in module_imports:
        uninstall(m)


@command()
@help_option("-h", is_flag=True, help="help")
@option("-x", is_flag=True, help="exclude comments")
@option("-i", is_flag=True, help="interactive")
@option("-d", is_flag=True, help="dry run")
@option("-v", is_flag=True, help="verbose")
@option("-f", help="crackerjack format: -f [module]")
def crackerjack(f, x, i, d, v):
    options = dict()
    if x:
        options["exclude"] = x
    if i:
        print("-i not currently implemented.")
        options["interactive"] = i
    if d:
        options["dry_run"] = d
    if v:
        print("-v not currently implemented.")
        options["verbose"] = v
    if f:
        crackerjack_it(f, **options)
