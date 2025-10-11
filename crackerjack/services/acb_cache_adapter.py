from acb.adapters import import_adapter
from acb.depends import depends

Cache = import_adapter("cache")

def get_cache():
    return depends.get(Cache)
