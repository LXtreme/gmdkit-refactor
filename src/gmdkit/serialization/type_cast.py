# Imports
from typing import Callable, Any
import base64

# Package Imports
from gmdkit.serialization import options
from gmdkit.utils.typing import NumKey


def to_bool(string:str) -> bool:
    return bool(int(string))


def from_bool(obj:bool) -> str:
    return str(int(bool(obj)))
    
    
def from_float(obj:float) -> str:
    # ContextVar.get() is surprisingly expensive when called millions of times
    # per round-trip.  In the normal case float_precision is None, so we skip
    # the lookup entirely using a cheap module-level flag that is only flipped
    # inside the casting_options() context manager.
    if not options._float_precision_active:
        if obj.is_integer():
            return str(int(obj))
        return str(obj)
    decimals = options.float_precision.get()
    return f"{obj:.{decimals}f}".rstrip('0').rstrip('.')

def to_string(obj:Any, **kwargs) -> str:
    if obj is None:
        return ""
    method = getattr(obj, "to_string", None)
    if callable(method):
        return method(**kwargs)

    if options.string_fallback.get():
        return str(obj)

    raise TypeError(f"Object of type {type(obj).__name__} is not serializable")


def to_numkey(key:str) -> NumKey:
    # isdigit() + int() scans the string twice.  try/except int() scans it
    # once and is faster for the overwhelmingly common all-digit case.
    try:
        return int(key)
    except ValueError:
        return key

def to_node(obj:Any, **kwargs) -> str:
    method = getattr(obj, "to_node", None)
    if callable(method):
        return method(**kwargs)

    if options.string_fallback.get():
        return str(obj)

    raise TypeError(f"Object of type {type(obj).__name__} is not serializable")


def from_optional(method:Callable):
    
    def from_string(string:str):
        if string == "":
            return None
        else:
            return method(string)
        
    return from_string


def to_optional(method:Callable):
    
    def to_string(obj:Any):
        if obj is None:
            return ""
        else:
            return method(obj)
        
    return to_string
    
    
def zip_string(obj:Any) -> str:
    
    string = getattr(obj, "string", None)
    if string is not None:
        return string
    
    if options.string_fallback.get():
        return str(obj)

    raise TypeError(f"Object of type {type(obj).__name__} is not serializable")


def decode_text(string:str) -> str:
    
    string_bytes = string.encode("utf-8")
    
    decoded_bytes = base64.urlsafe_b64decode(string_bytes)
    
    return decoded_bytes.decode("utf-8", errors="surrogateescape")


def encode_text(string:str) -> str:
    
    string_bytes = string.encode("utf-8", errors="surrogateescape")
    
    encoded_bytes = base64.urlsafe_b64encode(string_bytes)
    
    return encoded_bytes.decode("utf-8")

    
def serialize(obj:Any) -> str:
    # Ordered by frequency in a typical GD level: float >> int >> str >> other.
    # type() identity checks are faster than isinstance() for the common
    # primitives and avoid the bool-before-int subclass trap (bool IS an int).
    t = type(obj)

    if t is float:
        return from_float(obj)

    if t is int:
        return str(obj)

    if t is str:
        return obj

    if obj is None:
        return str()

    if t is bool:
        return from_bool(obj)

    return to_string(obj)


def dict_serializer(key:NumKey, value:Any):
    return (str(key), serialize(value))

        