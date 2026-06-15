#!/usr/bin/env python3
"""Audit each entry in FURB_TRANSFORMATIONS. Skips slow refurb subprocess calls;
compares handler output against the canonical 'good' form documented in refurb --explain.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

WT_PATH = "/Users/les/Projects/crackerjack/.claude/worktrees/wf_7d9ed37b-e05-1"


def load_agent():
    sys.path.insert(0, WT_PATH)
    from crackerjack.agents import refurb_agent as mod  # type: ignore

    return mod


# Minimal bad input per FURB code.
BAD_INPUTS: dict[str, str] = {
    "FURB102": "name = 'bob'\nif name.startswith('b') or name.startswith('B'):\n    pass\n",
    "FURB105": 'print("")\n',
    "FURB107": "try:\n    f()\nexcept FileNotFoundError:\n    pass\n",
    "FURB108": 'x = "a"\nif x == "abc" or x == "def":\n    pass\n',
    "FURB109": "nums = [str(x) for x in [1, 2, 3]]\n",
    "FURB110": "x = 1\ny = 2\nz = x if x else y\n",
    "FURB111": "predicate = lambda x: bool(x)\n",
    "FURB113": "nums = [1, 2, 3]\nnums.append(4)\nnums.append(5)\n",
    "FURB115": 'name = "bob"\nif len(name) == 0:\n    pass\n',
    "FURB116": "print(bin(1337)[2:])\n",
    "FURB117": "from pathlib import Path\npath = Path('filename')\nwith open(path) as f:\n    pass\n",
    "FURB118": "transform = lambda x: x[0]\n",
    "FURB119": 'print(f"{str(123)}")\n',
    "FURB122": "lines = ['a\\n', 'b\\n']\nwith open('x') as f:\n    for line in lines:\n        f.write(line)\n",
    "FURB123": "name = str('bob')\n",
    "FURB125": "def func():\n    print('hi')\n    return\n",
    "FURB126": "def index_or_default(nums, index, default):\n    if index >= len(nums):\n        return default\n    else:\n        return nums[index]\n",
    "FURB129": "with open('x') as f:\n    for line in f.readlines():\n        pass\n",
    "FURB131": "nums = [1, 2, 3]\ndel nums[:]\n",
    "FURB132": "nums = {123, 456}\nif 123 in nums:\n    nums.remove(123)\n",
    "FURB133": "def func():\n    for _ in range(10):\n        print('hi')\n        continue\n",
    "FURB134": "from functools import lru_cache\n@lru_cache(maxsize=None)\ndef f(x): return x + 1\n",
    "FURB136": "s1 = 90\ns2 = 99\nh = s1 if s1 > s2 else s2\n",
    "FURB138": "nums = [1, 2, 3, 4]\nodds = []\nfor n in nums:\n    if n % 2:\n        odds.append(n)\n",
    "FURB140": "scores = [85, 100, 60]\npassing = [60, 80, 70]\ndef passed(a, b): return a >= b\nr = all(passed(a, b) for a, b in zip(scores, passing))\n",
    "FURB141": "import os\nif os.path.exists('x'):\n    pass\n",
    "FURB142": "s = 'hello world'\nv = 'aeiou'\nletters = set(s)\nfor ch in v:\n    letters.discard(ch)\n",
    "FURB143": "def is_md(line):\n    return (line or '').startswith('#')\n",
    "FURB145": "nums = [1, 2, 3]\ncopy = nums[:]\n",
    "FURB148": "books = ['a', 'b']\nfor i, _ in enumerate(books):\n    print(i)\n",
    "FURB152": "def area(r):\n    return 3.1415 * r * r\n",
    "FURB156": "digits = '0123456789'\nif c in digits:\n    pass\n",
    "FURB157": "from decimal import Decimal\nif x == Decimal('0'):\n    pass\n",
    "FURB161": "x = bin(0b1010).count('1')\n",
    "FURB163": "import math\np = math.log(x, 10)\n",
    "FURB167": 'import re\nif re.match("^hello", "hi", re.I):\n    pass\n',
    "FURB168": "x = 1\nif isinstance(x, type(None)):\n    pass\n",
    "FURB169": "x = 1\nif type(x) is type(None):\n    pass\n",
    "FURB171": 'name = "x"\nif name in ("bob",):\n    pass\n',
    "FURB172": "from pathlib import Path\ndef is_md(f: Path):\n    return f.name.endswith('.md')\n",
    "FURB173": "def f(s):\n    return {'a': 1, **s}\n",
    "FURB175": "from fastapi import Query\ndef index(name: str = Query()):\n    return name\n",
    "FURB176": "from datetime import datetime\nnow = datetime.utcnow()\n",
    "FURB177": "from pathlib import Path\ncwd = Path().resolve()\n",
    "FURB180": "from abc import ABCMeta\nclass C(metaclass=ABCMeta):\n    pass\n",
    "FURB181": "from hashlib import sha512\nh = sha512(b'x').digest().hex()\n",
    "FURB183": 'num = f"{123}"\n',
    "FURB184": "def get_t(d):\n    t1 = ones(2,1)\n    t2 = t1.long()\n    t3 = t2.to(d)\n    return t3\n",
    "FURB185": 'd = {"a": 1}\nm = d.copy() | {"b": 2}\n',
    "FURB186": 'names = ["a","b"]\nnames = sorted(names)\n',
    "FURB187": 'names = ["a","b"]\nnames = names[::-1]\n',
    "FURB188": 'def f(x):\n    return x[:-4] if x.endswith(".txt") else x\n',
    "FURB189": "class D(dict):\n    pass\n",
    "FURB190": "import re\ndef f(x):\n    return re.sub(r'\\d', lambda d: d, x)\n",
}


# What each code SHOULD produce.
EXPECTED_OUTPUTS: dict[str, str] = {
    "FURB102": "name = 'bob'\nif name.startswith(('b', 'B')):\n    pass\n",
    "FURB105": "print()\n",
    "FURB107": "from contextlib import suppress\nwith suppress(FileNotFoundError):\n    f()\n",
    "FURB108": 'x = "a"\nif x in ("abc", "def"):\n    pass\n',
    "FURB109": "nums = [str(x) for x in (1, 2, 3)]\n",
    "FURB110": "x = 1\ny = 2\nz = x or y\n",
    "FURB111": "predicate = bool\n",
    "FURB113": "nums = [1, 2, 3]\nnums.extend((4, 5))\n",
    "FURB115": 'name = "bob"\nif not name:\n    pass\n',
    "FURB116": 'print(f"{1337:b}")\n',
    "FURB117": "from pathlib import Path\npath = Path('filename')\nwith path.open() as f:\n    pass\n",
    "FURB118": "from operator import itemgetter\ntransform = itemgetter(0)\n",
    "FURB119": 'print(f"{123}")\n',
    "FURB122": "lines = ['a\\n', 'b\\n']\nwith open('x') as f:\n    f.writelines(lines)\n",
    "FURB123": "name = 'bob'\n",
    "FURB125": "def func():\n    print('hi')\n",
    "FURB126": "def index_or_default(nums, index, default):\n    if index >= len(nums):\n        return default\n    return nums[index]\n",
    "FURB129": "with open('x') as f:\n    for line in f:\n        pass\n",
    "FURB131": "nums = [1, 2, 3]\nnums.clear()\n",
    "FURB132": "nums = {123, 456}\nnums.discard(123)\n",
    "FURB133": "def func():\n    for _ in range(10):\n        print('hi')\n",
    "FURB134": "from functools import cache\n@cache\ndef f(x): return x + 1\n",
    "FURB136": "s1 = 90\ns2 = 99\nh = max(s1, s2)\n",
    "FURB138": "nums = [1, 2, 3, 4]\nodds = [n for n in nums if n % 2]\n",
    "FURB140": "from itertools import starmap\nscores = [85, 100, 60]\npassing = [60, 80, 70]\ndef passed(a, b): return a >= b\nr = all(starmap(passed, zip(scores, passing)))\n",
    "FURB141": "from pathlib import Path\nif Path('x').exists():\n    pass\n",
    "FURB142": "s = 'hello world'\nv = 'aeiou'\nletters = set(s)\nletters.difference_update(v)\n",
    "FURB143": "def is_md(line):\n    return line.startswith('#')\n",
    "FURB145": "nums = [1, 2, 3]\ncopy = nums.copy()\n",
    "FURB148": "books = ['a', 'b']\nfor i in range(len(books)):\n    print(i)\n",
    "FURB152": "import math\ndef area(r):\n    return math.pi * r * r\n",
    "FURB156": "import string\nif c in string.digits:\n    pass\n",
    "FURB157": "from decimal import Decimal\nif x == Decimal(0):\n    pass\n",
    "FURB161": "x = 0b1010.bit_count()\n",
    "FURB163": "import math\np = math.log10(x)\n",
    "FURB167": 'import re\nif re.match("^hello", "hi", re.IGNORECASE):\n    pass\n',
    "FURB168": "x = 1\nif x is None:\n    pass\n",
    "FURB169": "x = 1\nif x is None:\n    pass\n",
    "FURB171": 'name = "x"\nif name == "bob":\n    pass\n',
    "FURB172": "from pathlib import Path\ndef is_md(f: Path):\n    return f.suffix == '.md'\n",
    "FURB173": "def f(s):\n    return {'a': 1} | s\n",
    "FURB175": "from fastapi import Query\ndef index(name: str):\n    return name\n",
    "FURB176": "from datetime import datetime, timezone\nnow = datetime.now(timezone.utc)\n",
    "FURB177": "from pathlib import Path\ncwd = Path.cwd()\n",
    "FURB180": "from abc import ABC\nclass C(ABC):\n    pass\n",
    "FURB181": "from hashlib import sha512\nh = sha512(b'x').hexdigest()\n",
    "FURB183": "num = str(123)\n",
    "FURB184": "def get_t(d):\n    return ones(2,1).long().to(d)\n",
    "FURB185": 'd = {"a": 1}\nm = d | {"b": 2}\n',
    "FURB186": 'names = ["a","b"]\nnames.sort()\n',
    "FURB187": 'names = ["a","b"]\nnames.reverse()\n',
    "FURB188": 'def f(x):\n    return x.removesuffix(".txt")\n',
    "FURB189": "from collections import UserDict\nclass D(UserDict):\n    pass\n",
    "FURB190": "import re\ndef f(x):\n    return re.sub(r'\\d', str, x)\n",
}


# Special verdicts where the canonical handler is correct for the wrong code.
# These flags are applied by hand below where the handler is mapped to the wrong FURB code.


def main() -> int:
    mod = load_agent()
    mapping = mod.FURB_TRANSFORMATIONS

    class DummyIssue:
        def __init__(self, ln: int | None = None) -> None:
            self.line_number = ln
            self.message = ""
            self.details: list[str] = []
            self.reason = ""
            self.file_path = None
            self.type = None

    class DummyCtx:
        pass

    # Build a bound agent without running __init__ (which expects real AgentContext)
    agent = mod.RefurbCodeTransformerAgent.__new__(mod.RefurbCodeTransformerAgent)
    mod.SubAgent.__init__(agent, DummyCtx())  # type: ignore[arg-type]

    print(f"AUDIT RESULTS - {len(mapping)} FURB transformations", flush=True)
    print("=" * 100, flush=True)
    print(f"{'CODE':<10} {'HANDLER':<35} {'VERDICT':<10} NOTES", flush=True)
    print("-" * 110, flush=True)

    counts: dict[str, int] = {}
    rows: list[tuple[str, str, str, str]] = []

    for code, handler_name in mapping.items():
        inp = BAD_INPUTS.get(code)
        exp = EXPECTED_OUTPUTS.get(code)
        handler: Callable | None = getattr(agent, handler_name, None)
        notes = ""
        verdict = "UNMAPPED"

        if inp is None:
            verdict = "UNMAPPED"
            notes = "no test input defined"
        elif exp is None:
            verdict = "UNMAPPED"
            notes = "no expected output defined"
        elif handler is None:
            verdict = "WRONG"
            notes = f"handler method {handler_name} does not exist on agent"
        else:
            issue = DummyIssue(ln=1)
            try:
                out, desc = handler(inp, issue)
            except Exception as e:
                verdict = "WRONG"
                notes = f"handler raised: {e}"
                out = inp
                desc = ""

            if out == inp:
                verdict = "NOOP"
                notes = (desc or "no change")[:80]
            else:
                matches = out.strip() == exp.strip()
                if matches:
                    verdict = "CORRECT"
                else:
                    verdict = "WRONG"
                    notes = f"observed:\n{out}\n---expected:\n{exp}"

        counts[verdict] = counts.get(verdict, 0) + 1
        rows.append((code, handler_name, verdict, notes))
        print(f"{code:<10} {handler_name:<35} {verdict:<10} {notes[:70]}", flush=True)

    print("-" * 110, flush=True)
    for v, c in sorted(counts.items()):
        print(f"  TOTAL {v:10s}  {c}", flush=True)

    # Detailed wrong findings
    print("\nDETAILED FINDINGS FOR WRONG/NOOP ROWS:\n", flush=True)
    for code, handler_name, verdict, notes in rows:
        if verdict not in ("WRONG", "NOOP", "UNMAPPED"):
            continue
        print(f"### {code}  ({handler_name}) - {verdict}", flush=True)
        if notes:
            print(notes, flush=True)
        print(flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
