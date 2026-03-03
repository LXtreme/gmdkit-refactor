# Imports
from contextvars import ContextVar
from contextlib import contextmanager


float_precision = ContextVar("float_precision", default=None) 
string_fallback = ContextVar("string_fallback", default=True)
discard_default = ContextVar("discard_default", default=False)

# Fast-path flag: stays False in the normal case so from_float() can skip the
# expensive ContextVar.get() call entirely.  Only flipped to True inside the
# casting_options() context manager when a custom precision is actually active.
_float_precision_active: bool = False


@contextmanager
def casting_options(
        float_precision:int|None=None,
        string_fallback:bool=False,
        discard_default:bool=False
        ):
    global _float_precision_active

    fp_var = globals()["float_precision"]
    sb_var = globals()["string_fallback"]
    dd_var = globals()["discard_default"]

    t_fp = fp_var.set(float_precision)
    t_sb = sb_var.set(string_fallback)
    t_dd = dd_var.set(discard_default)

    prev_active = _float_precision_active
    _float_precision_active = float_precision is not None

    try:
        yield
    finally:
        fp_var.reset(t_fp)
        sb_var.reset(t_sb)
        dd_var.reset(t_dd)
        _float_precision_active = prev_active