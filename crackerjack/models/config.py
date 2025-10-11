from acb.depends import depends
from crackerjack.config.settings import CrackerjackSettings

def get_workflow_options() -> CrackerjackSettings:
    return depends.get(CrackerjackSettings)
