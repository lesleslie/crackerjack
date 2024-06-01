import asyncio
import typing as t

from click import command, help_option, option
from pydantic import BaseModel
from crackerjack import crackerjack_it


class Options(BaseModel):
    commit: bool = False
    interactive: bool = False
    doc: bool = False
    do_not_update_configs: bool = False
    publish: t.Literal["micro", "minor", "major"] | bool = False
    bump: t.Literal["micro", "minor", "major"] | bool = False
    verbose: bool = False
    update_precommit: bool = False


options = Options()


@command()
@help_option("-h", is_flag=True, help="help")
@option("-c", is_flag=True, help="commit")
@option("-i", is_flag=True, help="interactive")
@option("-d", is_flag=True, help="doc")
@option("-x", is_flag=True, help="do not update configs")
@option("-u", is_flag=True, help="update pre-commit")
@option("-v", is_flag=True, help="verbose")
@option("-p", help="bump version and publish: -p [micro, minor, major]")
@option("-b", help="bump version: -b [micro, minor, major]")
# @option("-f", help="format: -f [module]")
def crackerjack(
    c: bool = False,
    i: bool = False,
    d: bool = False,
    u: bool = False,
    v: bool = False,
    x: bool = False,
    p: str | bool = False,
    b: str | bool = False,
) -> None:
    if c:
        options.commit = c
    if i:
        options.interactive = i
    if d:
        options.doc = d
    if u:
        options.update_precommit = u
    if x:
        options.do_not_update_configs = x
    if p in ("micro", "minor", "major"):
        options.publish = p
    if b in ("micro", "minor", "major"):
        options.bump = b
    if v:
        print("-v not currently implemented")
        options.verbose = v
    asyncio.run(crackerjack_it(options=options))


if __name__ == "__main__":
    crackerjack()
