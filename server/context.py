# utils/context.py

_context_store = {}

def _make_key(user_id, thread_id):
    return f"{user_id}:{thread_id}"

def set_context(user_id, thread_id, key, value):
    ctx_key = _make_key(user_id, thread_id)
    if ctx_key not in _context_store:
        _context_store[ctx_key] = {}
    _context_store[ctx_key][key] = value

def get_context(user_id, thread_id, key, default=None):
    ctx_key = _make_key(user_id, thread_id)
    return _context_store.get(ctx_key, {}).get(key, default)

def get_all_context(user_id, thread_id):
    ctx_key = _make_key(user_id, thread_id)
    return _context_store.get(ctx_key, {})

def clear_context(user_id, thread_id):
    ctx_key = _make_key(user_id, thread_id)
    _context_store.pop(ctx_key, None)
