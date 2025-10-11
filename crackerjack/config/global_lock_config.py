from acb.depends import depends
from crackerjack.config.settings import CrackerjackSettings, GlobalLockSettings

def get_global_lock_config() -> GlobalLockSettings:
    return depends.get(CrackerjackSettings).global_lock
