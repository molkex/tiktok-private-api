"""
Minimal protobuf encoder / decoder for X-Argus payloads.

Supports wire types:
  0 - VARINT
  1 - 64-bit (fixed INT64)
  2 - Length-delimited (STRING / bytes / nested message)
  5 - 32-bit (fixed INT32)

Ported from douyin-sign/sign/protobuf.py (cleaner than tiktok-api variant).
"""

from __future__ import annotations

from enum import IntEnum, unique


class ProtoError(Exception):
    def __init__(self, msg: str):
        self.msg = msg

    def __str__(self) -> str:
        return repr(self.msg)


@unique
class ProtoFieldType(IntEnum):
    VARINT = 0
    INT64 = 1
    STRING = 2       # length-delimited (bytes / nested message / utf-8)
    GROUPSTART = 3   # deprecated, not used by Argus
    GROUPEND = 4     # deprecated, not used by Argus
    INT32 = 5


class ProtoField:
    __slots__ = ("idx", "type", "val")

    def __init__(self, idx: int, typ: ProtoFieldType, val):
        self.idx = idx
        self.type = typ
        self.val = val

    def is_ascii(self) -> bool:
        if not isinstance(self.val, bytes):
            return False
        return all(0x20 <= b <= 0x7E for b in self.val)

    def __repr__(self) -> str:
        if self.type in (ProtoFieldType.INT32, ProtoFieldType.INT64, ProtoFieldType.VARINT):
            return f"{self.idx}({self.type.name}): {self.val}"
        if self.type == ProtoFieldType.STRING:
            if self.is_ascii():
                return f'{self.idx}({self.type.name}): "{self.val.decode("ascii")}"'
            return f'{self.idx}({self.type.name}): h"{self.val.hex()}"'
        return f"{self.idx}({self.type.name}): {self.val}"


# ---------------------------------------------------------------------------
# Low-level reader / writer
# ---------------------------------------------------------------------------

class ProtoReader:
    """Sequential reader over a ``bytes`` buffer."""

    __slots__ = ("data", "pos")

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def remaining(self, length: int) -> bool:
        return self.pos + length <= len(self.data)

    def read_byte(self) -> int:
        assert self.remaining(1)
        b = self.data[self.pos] & 0xFF
        self.pos += 1
        return b

    def read(self, length: int) -> bytes:
        assert self.remaining(length)
        out = self.data[self.pos : self.pos + length]
        self.pos += length
        return out

    def read_int32(self) -> int:
        return int.from_bytes(self.read(4), "little", signed=False)

    def read_int64(self) -> int:
        return int.from_bytes(self.read(8), "little", signed=False)

    def read_varint(self) -> int:
        result = 0
        shift = 0
        while True:
            b = self.read_byte()
            result |= (b & 0x7F) << shift
            if b < 0x80:
                break
            shift += 7
        return result

    def read_string(self) -> bytes:
        length = self.read_varint()
        return self.read(length)


class ProtoWriter:
    """Sequential writer into a ``bytearray``."""

    __slots__ = ("data",)

    def __init__(self):
        self.data = bytearray()

    def write_byte(self, b: int) -> None:
        self.data.append(b & 0xFF)

    def write(self, bs: bytes) -> None:
        self.data.extend(bs)

    def write_int32(self, val: int) -> None:
        self.write(val.to_bytes(4, "little", signed=False))

    def write_int64(self, val: int) -> None:
        self.write(val.to_bytes(8, "little", signed=False))

    def write_varint(self, val: int) -> None:
        while val > 0x7F:
            self.write_byte((val & 0x7F) | 0x80)
            val >>= 7
        self.write_byte(val & 0x7F)

    def write_string(self, bs: bytes) -> None:
        self.write_varint(len(bs))
        self.write(bs)

    def to_bytes(self) -> bytes:
        return bytes(self.data)


# ---------------------------------------------------------------------------
# High-level ProtoBuf message
# ---------------------------------------------------------------------------

class ProtoBuf:
    """
    Minimal protobuf message container.

    Construct from raw ``bytes``, a ``dict``, or empty::

        msg = ProtoBuf(raw_bytes)          # parse
        msg = ProtoBuf({1: 42, 2: "hi"})   # from dict
        msg = ProtoBuf()                    # empty, add fields manually
        raw = msg.to_buf()                  # serialize
    """

    def __init__(self, data: bytes | dict | None = None):
        self.fields: list[ProtoField] = []
        if data is not None:
            if isinstance(data, bytes) and len(data) > 0:
                self._parse_buf(data)
            elif isinstance(data, dict) and len(data) > 0:
                self._parse_dict(data)

    # -- subscript access ---------------------------------------------------

    def __getitem__(self, idx):
        pf = self.get(int(idx))
        if pf is None:
            return None
        if pf.type != ProtoFieldType.STRING:
            return pf.val
        if not isinstance(idx, int):
            return pf.val
        if pf.val is None:
            return None
        if pf.is_ascii():
            return pf.val.decode("utf-8")
        return ProtoBuf(pf.val)

    # -- deserialization -----------------------------------------------------

    def _parse_buf(self, raw: bytes) -> None:
        reader = ProtoReader(raw)
        while reader.remaining(1):
            key = reader.read_varint()
            wire = ProtoFieldType(key & 0x7)
            field_idx = key >> 3
            if field_idx == 0:
                break
            if wire == ProtoFieldType.INT32:
                self.put(ProtoField(field_idx, wire, reader.read_int32()))
            elif wire == ProtoFieldType.INT64:
                self.put(ProtoField(field_idx, wire, reader.read_int64()))
            elif wire == ProtoFieldType.VARINT:
                self.put(ProtoField(field_idx, wire, reader.read_varint()))
            elif wire == ProtoFieldType.STRING:
                self.put(ProtoField(field_idx, wire, reader.read_string()))
            else:
                raise ProtoError(f"Unexpected wire type: {wire.name}")

    # -- serialization -------------------------------------------------------

    def to_buf(self) -> bytes:
        w = ProtoWriter()
        for f in self.fields:
            tag = (f.idx << 3) | (f.type & 7)
            w.write_varint(tag)
            if f.type == ProtoFieldType.INT32:
                w.write_int32(f.val)
            elif f.type == ProtoFieldType.INT64:
                w.write_int64(f.val)
            elif f.type == ProtoFieldType.VARINT:
                w.write_varint(f.val)
            elif f.type == ProtoFieldType.STRING:
                w.write_string(f.val)
            else:
                raise ProtoError(f"Cannot encode wire type: {f.type.name}")
        return w.to_bytes()

    # -- field access --------------------------------------------------------

    def get(self, idx: int) -> ProtoField | None:
        for f in self.fields:
            if f.idx == idx:
                return f
        return None

    def get_list(self, idx: int) -> list[ProtoField]:
        return [f for f in self.fields if f.idx == idx]

    def get_int(self, idx: int) -> int:
        pf = self.get(idx)
        if pf is None:
            return 0
        if pf.type in (ProtoFieldType.INT32, ProtoFieldType.INT64, ProtoFieldType.VARINT):
            return pf.val
        raise ProtoError(f"get_int({idx}) -> {pf.type}")

    def get_bytes(self, idx: int) -> bytes | None:
        pf = self.get(idx)
        if pf is None:
            return None
        if pf.type == ProtoFieldType.STRING:
            return pf.val
        raise ProtoError(f"get_bytes({idx}) -> {pf.type}")

    def get_utf8(self, idx: int) -> str | None:
        bs = self.get_bytes(idx)
        return bs.decode("utf-8") if bs is not None else None

    def get_protobuf(self, idx: int) -> ProtoBuf | None:
        bs = self.get_bytes(idx)
        return ProtoBuf(bs) if bs is not None else None

    # -- field insertion -----------------------------------------------------

    def put(self, field: ProtoField) -> None:
        self.fields.append(field)

    def put_int32(self, idx: int, val: int) -> None:
        self.put(ProtoField(idx, ProtoFieldType.INT32, val))

    def put_int64(self, idx: int, val: int) -> None:
        self.put(ProtoField(idx, ProtoFieldType.INT64, val))

    def put_varint(self, idx: int, val: int) -> None:
        self.put(ProtoField(idx, ProtoFieldType.VARINT, val))

    def put_bytes(self, idx: int, data: bytes) -> None:
        self.put(ProtoField(idx, ProtoFieldType.STRING, data))

    def put_utf8(self, idx: int, data: str) -> None:
        self.put(ProtoField(idx, ProtoFieldType.STRING, data.encode("utf-8")))

    def put_protobuf(self, idx: int, data: ProtoBuf) -> None:
        self.put(ProtoField(idx, ProtoFieldType.STRING, data.to_buf()))

    # -- dict interop -------------------------------------------------------

    def _parse_dict(self, data: dict) -> None:
        for k, v in data.items():
            if isinstance(v, int):
                self.put_varint(k, v)
            elif isinstance(v, str):
                self.put_utf8(k, v)
            elif isinstance(v, bytes):
                self.put_bytes(k, v)
            elif isinstance(v, dict):
                self.put_protobuf(k, ProtoBuf(v))
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, int):
                        self.put_varint(k, item)
                    elif isinstance(item, str):
                        self.put_utf8(k, item)
                    elif isinstance(item, bytes):
                        self.put_bytes(k, item)
            else:
                raise ProtoError(f"Unsupported type {type(v)} for protobuf field")

    def to_dict(self, template: dict) -> dict:
        out = dict(template)
        for k, v in out.items():
            if isinstance(v, int):
                out[k] = self.get_int(k)
            elif isinstance(v, str):
                out[k] = self.get_utf8(k)
            elif isinstance(v, bytes):
                out[k] = self.get_bytes(k)
            elif isinstance(v, dict):
                sub = self.get_protobuf(k)
                out[k] = sub.to_dict(v) if sub else v
            else:
                raise ProtoError(f"Unsupported template type {type(v)}")
        return out

    def dump(self) -> None:
        for f in self.fields:
            print(f)
