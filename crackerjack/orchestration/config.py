from acb.depends import depends
from crackerjack.config.settings import CrackerjackSettings

def get_orchestration_config() -> CrackerjackSettings:
    return depends.get(CrackerjackSettings)
