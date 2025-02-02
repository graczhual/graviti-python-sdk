#!/usr/bin/env python3

# pylint: disable-all
# type: ignore
# flake8: noqa

"""Code converting PyArrow schema to Avro Schema."""

from graviti.portex.base import PortexType
from graviti.portex.builtin import (
    array,
    binary,
    boolean,
    enum,
    float32,
    float64,
    int32,
    int64,
    record,
    string,
)

_REMOTE_FILE_FIELD_NAMES = {"checksum", "url"}

_PRIMITIVE_TYPES = {
    int32: "int",
    int64: "int",
    float32: "float",
    float64: "double",
    boolean: "boolean",
    string: "string",
    binary: "bytes",
}


class AvroSchema:
    def __init__(self):
        pass

    def to_json(self):
        return {}


class AvroField:
    def __init__(
        self,
        name_registry,
        typ: AvroSchema,
        name,
        optional=True,
        has_default=False,
        default=None,
    ):
        self._type = typ
        self._name = name
        self._optional = optional
        self._has_default = has_default
        self._default = default

    def to_json(self):
        if self._optional:
            result = {
                "name": self._name,
                "type": [
                    "null",
                    self._type.to_json(),
                ],
            }
        else:
            result = {
                "name": self._name,
                "type": self._type.to_json(),
            }
        if self._has_default:
            result["default"] = self._default

        return result


class AvroPrimitiveSchema(AvroSchema):
    def __init__(self, typ, has_default=False, default=None):
        super().__init__()
        self._default = default
        self._has_default = has_default
        self._type = typ

    def to_json(self):
        if self._has_default:
            return {"type": self._type, "default": self._default}
        else:
            return self._type


class AvroRecordSchema(AvroSchema):
    def __init__(self, name_registry, name, namespace, fields: [], aliases=None):
        super().__init__()
        self._name = name
        self._namespace = namespace
        self._fields = fields

        self._aliases = aliases
        if self._aliases is None:
            self._aliases = []

    def to_json(self):
        return {
            "type": "record",
            "name": self._name,
            "namespace": self._namespace,
            "aliases": self._aliases,
            "fields": [field.to_json() for field in self._fields],
        }


class AvroArraySchema(AvroSchema):
    def __init__(self, items: AvroSchema):
        super().__init__()
        self._items = items

    def to_json(self):
        return {
            "type": "array",
            "items": self._items.to_json(),
            "default": [],
        }


class AvroEnumSchema(AvroSchema):
    def __init__(self, namespace, name, symbols):
        super().__init__()
        self._namespace = namespace
        self._name = name
        self._symbols = symbols

    def to_json(self):
        return {
            "type": "enum",
            "namespace": self._namespace,
            "name": self._name,
            "symbols": self._symbols,
        }


def _on_list(names, namespace, name, _pa_ist: array) -> AvroArraySchema:
    sub_namespace = f"{namespace}.{name}.items"
    sub_name = "items"
    items = _on_type(names, sub_namespace, sub_name, _pa_ist.items.to_builtin())
    return AvroArraySchema(items=items)


def _on_primitive(portex_type: PortexType) -> AvroSchema:
    try:
        return AvroPrimitiveSchema(typ=_PRIMITIVE_TYPES[type(portex_type)])
    except KeyError:
        raise Exception(f"unsupported type {portex_type}") from None


def _on_struct(names, namespace, name, _struct: record) -> AvroRecordSchema:
    avro_record_fields = list()
    skip_url = False

    # remove "url" field in avro schema
    if set(_struct.keys()) == _REMOTE_FILE_FIELD_NAMES:
        skip_url = True

    for sub_name, sub_type in _struct.items():
        if skip_url and sub_name == "url":
            continue

        sub_type = sub_type.to_builtin()
        sub_namespace = f"{namespace}.{name}"
        sub_schema = _on_type(names, sub_namespace, sub_name, sub_type)
        avro_record_field = AvroField(
            typ=sub_schema,
            name=sub_name,
            has_default=False,
            name_registry=names,
        )
        avro_record_fields.append(avro_record_field)

    return AvroRecordSchema(
        name=name, namespace=namespace, fields=avro_record_fields, name_registry=names
    )


def _on_enum(name_registry, namespace, name, _filed: enum) -> AvroPrimitiveSchema:
    return AvroPrimitiveSchema("int")


def _on_type(names, namespace, name, _portex_type):
    typ = type(_portex_type)
    if typ in _COMPLEX_TYPES_PROCESSERS:
        return _COMPLEX_TYPES_PROCESSERS[typ](names, namespace, name, _portex_type)

    return _on_primitive(_portex_type)


def convert_portex_schema_to_avro(_schema: record):
    avro_schema = _on_struct([], "cn.graviti.portex", "root", _schema)
    return avro_schema.to_json()


_COMPLEX_TYPES_PROCESSERS = {
    record: _on_struct,
    array: _on_list,
    enum: _on_enum,
}
