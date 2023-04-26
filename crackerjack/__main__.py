import asyncio

from addict import Dict as adict
from click import command
from click import help_option
from click import option
from crackerjack import crackerjack_it


@command()
@help_option("-h", is_flag=True, help="help")
@option("-c", is_flag=True, help="commit")
@option("-i", is_flag=True, help="interactive")
@option("-d", is_flag=True, help="debug")
@option("-v", is_flag=True, help="verbose")
@option("-p", help="publish: -p [micro, minor, major]")
# @option("-f", help="format: -f [module]")
def crackerjack(c: bool, i: bool, d: bool, v: bool, p: str) -> None:
    options: adict[str, str | bool] = adict()
    if c:
        options["commit"] = c
    if i:
        print("-i not currently implemented.")
        options["interactive"] = i
    if d:
        options["debug"] = d
    if p in ("micro", "minor", "major"):
        options["publish"] = p
    if v:
        print("-v not currently implemented.")
        options["verbose"] = v
    asyncio.run(crackerjack_it(options))


if __name__ == "__main__":
    crackerjack()
