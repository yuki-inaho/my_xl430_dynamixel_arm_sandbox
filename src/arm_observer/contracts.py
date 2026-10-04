"""Generate the exchange schema from the same dataclasses used during acquisition."""

import types
from dataclasses import fields, is_dataclass
from typing import Literal, get_args, get_origin, get_type_hints

from arm_observer.models import EndEvent, FrameEvent, MetadataEvent


def schema_for(annotation: object, definitions: dict[str, object]) -> dict[str, object]:
    primitives: dict[object, str] = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        type(None): "null",
    }
    if annotation in primitives:
        return {"type": primitives[annotation]}
    origin, arguments = get_origin(annotation), get_args(annotation)
    if origin is Literal:
        return {"enum": list(arguments)}
    if origin is types.UnionType:
        return {"anyOf": [schema_for(item, definitions) for item in arguments]}
    if origin is tuple:
        return {"type": "array", "items": schema_for(arguments[0], definitions)}
    if isinstance(annotation, type) and is_dataclass(annotation):
        return dataclass_schema(annotation, definitions)
    raise TypeError(f"Unsupported exchange type: {annotation}")


def dataclass_schema(record_type: type, definitions: dict[str, object]) -> dict[str, object]:
    if not is_dataclass(record_type):
        raise TypeError(f"Not a dataclass: {record_type}")
    name = record_type.__name__
    if name not in definitions:
        definitions[name] = {}
        hints = get_type_hints(record_type)
        properties = {
            field.name: schema_for(hints[field.name], definitions) for field in fields(record_type)
        }
        refine_integer_ranges(properties)
        definitions[name] = {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
            "required": [name for name in properties
                         if name not in ("simulated", "acquisition_id")],
        }
    return {"$ref": f"#/$defs/{name}"}


def refine_integer_ranges(properties: dict[str, dict[str, object]]) -> None:
    bounds = {
        "motor_id": (0, 252),
        "model_number": (0, 65535),
        "firmware_version": (0, 255),
        "device_error": (0, 255),
        "hardware_error": (0, 255),
        "moving_status": (0, 255),
        "temperature_c": (0, 255),
        "voltage_raw": (0, 65535),
        "tick_ms": (0, 65535),
        "address": (0, 65535),
        "size": (0, 255),
        "raw": (0, 2**32 - 1),
        "value": (-(2**63), 2**63 - 1),
        "comm_result": (-(2**31), 2**31 - 1),
        "position_counts": (-(2**31), 2**31 - 1),
        "velocity_raw": (-(2**31), 2**31 - 1),
        "pwm_raw": (-32768, 32767),
        "load_raw": (-32768, 32767),
        "baudrate": (0, 2**32 - 1),
    }
    bounds.update(
        dict.fromkeys(
            ("sequence", "monotonic_ns", "frames", "incomplete_frames", "deadline_misses"),
            (0, 2**64 - 1),
        )
    )
    for name, (minimum, maximum) in bounds.items():
        if name in properties:
            properties[name].update(minimum=minimum, maximum=maximum)
    if "expected_ids" in properties:
        properties["expected_ids"].update(
            items={"type": "integer", "minimum": 0, "maximum": 252},
            uniqueItems=True,
            minItems=1,
        )


def stream_schema() -> dict[str, object]:
    definitions: dict[str, object] = {}
    records = [schema_for(record, definitions) for record in (MetadataEvent, FrameEvent, EndEvent)]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:my-dynamixel-arm:stream:v2",
        "oneOf": records,
        "$defs": definitions,
    }
