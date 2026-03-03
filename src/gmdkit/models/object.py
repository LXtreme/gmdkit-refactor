# Imports
from typing import Self, Optional

# Package Imports
from gmdkit.utils.types import ListClass, DictClass
from gmdkit.serialization.mixins import (
    DictDecoderMixin, 
    ArrayDecoderMixin,
    PlistDecoderMixin,
    FilePathMixin,
    DelimiterMixin,
    FileStringMixin,
    LoadPlistContentMixin
    )
from gmdkit.serialization.type_cast import serialize, to_numkey
from gmdkit.serialization.functions import dict_cast, write_plist, kv_wrap
from gmdkit.casting.object_props import PROPERTY_DECODERS, PROPERTY_ENCODERS
from gmdkit.defaults.objects import OBJECT_DEFAULT

# ---------------------------------------------------------------------------
# Pre-computed unified lookup tables for the Object hot-path serializers.
#
# _ENCODE_TABLE  maps  int_key -> (str_key, encode_func)
#   - str_key is pre-computed so we never call str(key) at encode time.
#   - encode_func is the specific encoder from PROPERTY_ENCODERS, or str() as
#     the fallback.  All unregistered properties decode to int or IntEnum
#     (which is a subclass of int), so str() is always correct.
#
# _DECODE_TABLE  maps  int_key -> decode_func  (plain copy of PROPERTY_DECODERS)
#   - Keys absent from the table are left as raw strings (no-op).
#
# Both are module-level so the dict.get call inside the hot loop binds once.
# ---------------------------------------------------------------------------

_ALL_PROP_KEYS: frozenset = frozenset(PROPERTY_DECODERS) | frozenset(PROPERTY_ENCODERS)

_ENCODE_TABLE: dict = {
    k: (str(k), PROPERTY_ENCODERS[k] if k in PROPERTY_ENCODERS else str)
    for k in _ALL_PROP_KEYS
}
_ENCODE_TABLE_GET = _ENCODE_TABLE.get

_DECODE_TABLE: dict = dict(PROPERTY_DECODERS)
_DECODE_TABLE_GET = _DECODE_TABLE.get


class Object(DelimiterMixin,DictDecoderMixin,DictClass):
    
    SEPARATOR = ","
    END_DELIMITER = ";"
    DECODER = staticmethod(dict_cast(PROPERTY_DECODERS,key_start=to_numkey))
    ENCODER = staticmethod(dict_cast(PROPERTY_ENCODERS,key_end=str,default=serialize))
    DEFAULTS = OBJECT_DEFAULT

    @classmethod
    def default(cls, object_id:int) -> Self:
                
        string = cls.DEFAULTS.get(object_id, f"1,{object_id},2,0,3,0;")
        
        return cls.from_string(string)

    @classmethod
    def from_string(cls, string: str, **kwargs) -> "Object":  # type: ignore[override]
        """Fast-path decoder: parse key,value,key,value,... directly.

        Bypasses the DictDecoderMixin machinery (token list allocation,
        cast_func closure dispatch, tuple unpacking via ``for part in
        encoder(k, v)``) which adds up enormously over 300K+ objects.
        Falls back to the generic path for malformed input.
        """
        if not string:
            return cls()

        # ObjectList keeps the ";" separator on each token, so strip it.
        if string.endswith(";"):
            string = string[:-1]

        tokens = string.split(",")

        if len(tokens) % 2 != 0:
            # Odd token count — let the generic path raise a clear error.
            return super().from_string(string + ";", **kwargs)

        result = cls()
        for raw_key, raw_val in zip(tokens[::2], tokens[1::2]):
            # Most keys are plain integers; a small number in the start object
            # use string prefixes like "kS38" or "kA13".
            try:
                key = int(raw_key)
            except ValueError:
                key = raw_key
            func = _DECODE_TABLE_GET(key)
            result[key] = func(raw_val) if func is not None else raw_val

        return result

    def to_string(self, **kwargs) -> str:  # type: ignore[override]
        """Fast-path encoder: build key,value,key,value,...; directly.

        Uses a single dict lookup per property (returning both the
        pre-computed str key and the encoder) instead of the two lookups
        and a str(key) call that the generic path requires.  All
        unregistered values are int/IntEnum, so str() is a safe fallback.
        """
        parts: list[str] = []
        append = parts.append

        for key, value in self.items():
            entry = _ENCODE_TABLE_GET(key)
            if entry is not None:
                str_key, enc = entry
                append(str_key)
                append(enc(value))
            else:
                # Unknown key — not in either property table (rare edge case).
                append(str(key))
                append(str(value))

        if not parts:
            return ""
        return ",".join(parts) + ";"


class ObjectList(ArrayDecoderMixin,ListClass):
    
    SEPARATOR = ";"
    KEEP_SEPARATOR = True
    DECODER = Object.from_string
    ENCODER = Object.to_string
    

class ObjectGroup(FileStringMixin):
    
    __slots__ = ("string","objects")
    
    def __init__(self, string:Optional[str]=None):
        self.string = string or str()
    
    
    def load(self, string:Optional[str]=None) -> ObjectList:
        
        string = self.string if string is None else string
        
        self.objects = ObjectList.from_string(string)
        
        return self.objects
    
    
    def save(self, objects:Optional[ObjectList]=None) -> str:
        objects = getattr(self, "objects", None) if objects is not None else objects
    
        if objects is None:
            return self.string
    
        self.string = objects.to_string()
        
        return self.string
    
    
    @classmethod
    def from_string(cls, string:str, load_content:bool=True):
        
        new = cls(string)
        
        if load_content:
            new.load()
            
        return new
    
    
    def to_string(self, save_content:bool=True):
        
        if save_content:
            self.save()
        
        return self.string


class ObjectGroupDict(LoadPlistContentMixin,FilePathMixin,PlistDecoderMixin,DictClass):
    DECODER = staticmethod(kv_wrap(int,ObjectGroup))
    ENCODER = staticmethod(kv_wrap(str,lambda x: write_plist(x.to_string())))
    EXTENSION = "plist"
    LOAD_CONTENT = False
    
    def _name_fallback_(self):
        return "objectgroup"