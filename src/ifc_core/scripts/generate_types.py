import inspect
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Union, get_args, get_origin

try:
    from pydantic import BaseModel
except ImportError:
    print("Pydantic not found. Please install it to use this script.")
    sys.exit(1)

# Ensure ifc_core is in path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ifc_core.models import groups, ids, ifc


def resolve_output_path() -> Path:
    """Determine output location for generated types.

    Logic:
    1. Command line argument (python generate_types.py path/to/file.ts)
    2. Fallback to "./ifc_core.ts" in the script's directory.
    """
    if len(sys.argv) > 1:
        return Path(sys.argv[1])

    return Path(__file__).resolve().parent / "ifc_core.ts"


TS_TYPE_MAP = {
    str: "string",
    int: "number",
    float: "number",
    bool: "boolean",
    Any: "any",
    type(None): "null",
}


def get_ts_type(py_type: Any) -> str:
    """Recursively convert Python types to TypeScript types."""
    origin = get_origin(py_type)
    args = get_args(py_type)

    if py_type in TS_TYPE_MAP:
        return TS_TYPE_MAP[py_type]

    if origin is list or origin is list:
        return f"{get_ts_type(args[0])}[]"

    if origin is dict or origin is dict:
        return f"{{ [key: {get_ts_type(args[0])}]: {get_ts_type(args[1])} }}"

    if origin is Union:
        # Filter out NoneType for Optional
        non_null_args = [a for a in args if a is not type(None)]
        ts_args = [get_ts_type(a) for a in non_null_args]
        if len(ts_args) == 1:
            # It was Optional[T]
            return ts_args[0]
        # Sort and join with pipe
        return f"({' | '.join(ts_args)})"

    if hasattr(py_type, "__forward_arg__"):
        return py_type.__forward_arg__

    if inspect.isclass(py_type):
        if issubclass(py_type, Enum):
            return py_type.__name__
        if issubclass(py_type, BaseModel):
            return py_type.__name__

    return "any"


def generate_ts(output_path: Path):
    lines = [
        "/**",
        " * AUTO-GENERATED FILE - DO NOT EDIT MANUALLY",
        " * Source: ifc-core Pydantic models",
        " */",
        "",
    ]

    # Collect all models and enums from the modules
    modules = [ifc, ids, groups]
    processed_names = set()

    classes_to_process = []
    for mod in modules:
        for name, obj in inspect.getmembers(mod):
            if inspect.isclass(obj) and obj.__module__.startswith("ifc_core.models"):
                if issubclass(obj, (BaseModel, Enum)) and obj not in [BaseModel, Enum]:
                    if obj.__name__ not in processed_names:
                        classes_to_process.append(obj)
                        processed_names.add(obj.__name__)

    # Sort so dependencies (Enums) usually come first if possible, but TS is hoisted so not strictly required
    for obj in classes_to_process:
        if issubclass(obj, Enum):
            lines.append(f"export type {obj.__name__} =")
            enum_values = [f"  | '{e.value}'" for e in obj]
            lines.extend(enum_values)
            lines.append(";")
            lines.append("")

        elif issubclass(obj, BaseModel):
            lines.append(f"export interface {obj.__name__} {{")

            # Use __annotations__ to get types
            for field_name, field_type in obj.__annotations__.items():
                ts_type = get_ts_type(field_type)

                # Check if it has a default Value (Optionality)
                is_optional = False
                if get_origin(field_type) is Union and type(None) in get_args(
                    field_type
                ):
                    is_optional = True

                # Manual override for some recursive cases if needed
                if field_name == "children" and obj.__name__ in [
                    "SpatialNode",
                    "ClassificationNode",
                ]:
                    # Ensure it matches the TS recursive type
                    ts_type = f"{obj.__name__}[]"

                opt_char = "?" if is_optional else ""
                lines.append(f"  {field_name}{opt_char}: {ts_type};")

            lines.append("}")
            lines.append("")

    content = "\n".join(lines)

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Successfully generated types to {output_path}")


if __name__ == "__main__":
    out = resolve_output_path()
    generate_ts(out)
