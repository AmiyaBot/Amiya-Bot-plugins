from core.database.bot import Pool

def get_pool_name(pool:Pool):
    if pool.pool_title:
        return pool.pool_title
    return pool.pool_name

def get_pool_id(pool:Pool):
    if pool.is_official is None or pool.is_official:
        return pool.pool_name
    return "Custom-"-pool.pool_name