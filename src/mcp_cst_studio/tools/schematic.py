"""Design Studio schematic tools for CST Studio Suite."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from mcp.types import TextContent, Tool

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.validators import ValidationError, validate_name, validate_positive

if TYPE_CHECKING:
    from mcp.server import Server


_RLC_SPECS = {
    "resistor": {
        "block_type": r"CircuitBasic\Resistor",
        "property_name": "Resistance",
        "unit": "Ohm",
    },
    "inductor": {
        "block_type": r"CircuitBasic\Inductor",
        "property_name": "Inductance",
        "unit": "H",
    },
    "capacitor": {
        "block_type": r"CircuitBasic\Capacitor",
        "property_name": "Capacitance",
        "unit": "F",
    },
}

_COMPONENT_TYPE_ALIASES = {
    "block": "Block",
    "externalport": "Externalport",
    "external_port": "Externalport",
    "external port": "Externalport",
    "port": "Externalport",
    "probe": "Probe",
}


TOOLS: list[Tool] = [
    Tool(
        name="cst_schematic_create_rlc",
        description=(
            "Create a Design Studio schematic resistor, inductor, or capacitor. "
            "Connected mode calls project.schematic.Block directly; offline mode "
            "returns equivalent Design Studio VBA."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": sorted(_RLC_SPECS),
                    "description": "Component kind: resistor, inductor, or capacitor.",
                },
                "name": {"type": "string", "description": "Schematic block name."},
                "value": {
                    "type": ["number", "string"],
                    "description": "Component value or CST parameter expression.",
                },
                "x": {"type": "number", "description": "Schematic X position."},
                "y": {"type": "number", "description": "Schematic Y position."},
                "rotation": {
                    "type": "integer",
                    "description": "Optional schematic rotation angle in degrees.",
                },
            },
            "required": ["kind", "name", "value"],
        },
    ),
    Tool(
        name="cst_schematic_create_external_port",
        description=(
            "Create a Design Studio schematic external port. Connected mode calls "
            "project.schematic.ExternalPort directly; offline mode returns VBA."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "External port name."},
                "x": {"type": "number", "description": "Schematic X position."},
                "y": {"type": "number", "description": "Schematic Y position."},
                "number": {"type": "integer", "description": "Optional port number."},
                "impedance": {
                    "type": ["number", "string"],
                    "description": "Optional port impedance in Ohm or a CST expression.",
                },
                "label": {"type": "string", "description": "Optional schematic label."},
            },
            "required": ["name"],
        },
    ),
    Tool(
        name="cst_schematic_connect",
        description=(
            "Connect Design Studio schematic component ports into one net. Ports "
            "are entries such as {'component_type':'Block','name':'R1','port_index':1}."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "net_name": {"type": "string", "description": "Final schematic net name."},
                "ports": {
                    "type": "array",
                    "minItems": 2,
                    "items": {
                        "type": "object",
                        "properties": {
                            "component_type": {
                                "type": "string",
                                "description": "Block, ExternalPort, or Probe.",
                            },
                            "name": {"type": "string", "description": "Component name."},
                            "port_index": {
                                "type": "integer",
                                "description": "CST schematic port index.",
                            },
                        },
                        "required": ["component_type", "name", "port_index"],
                    },
                },
                "show_label": {
                    "type": "boolean",
                    "description": "Show the net-name label on the schematic.",
                    "default": False,
                },
            },
            "required": ["net_name", "ports"],
        },
    ),
    Tool(
        name="cst_schematic_list",
        description=(
            "List Design Studio schematic blocks and nets from the active CST project. "
            "Requires connected mode."
        ),
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="cst_schematic_list_objects",
        description=(
            "List public members exposed by project.schematic. Use this to discover "
            "CST Design Studio schematic objects such as Block, Net, ExternalPort, "
            "SimulationTask, Optimizer, and their method counts."
        ),
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="cst_schematic_object_methods",
        description=(
            "List public methods for one project.schematic object, for example "
            "Block, Net, ExternalPort, SchematicLayout, SimulationTask, or Optimizer."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "Schematic object name, e.g. Block or Net.",
                },
            },
            "required": ["object_name"],
        },
    ),
    Tool(
        name="cst_schematic_call",
        description=(
            "Call any public method on a project.schematic object. This is the "
            "generic bridge for CST schematic RemoteObjects: it invokes "
            "project.schematic.<object_name>.<method_name>(*args, **kwargs). "
            "Use the specialized tools for common RLC/port/net operations when possible."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "Schematic object name, e.g. Block, Net, or SimulationTask.",
                },
                "method_name": {
                    "type": "string",
                    "description": "Public method name to call on the object.",
                },
                "args": {
                    "type": "array",
                    "description": "Positional arguments passed to the CST method.",
                    "default": [],
                },
                "kwargs": {
                    "type": "object",
                    "description": "Keyword arguments passed to the CST method.",
                    "default": {},
                },
            },
            "required": ["object_name", "method_name"],
        },
    ),
]


def _text(data: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2))]


def _format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        raise ValidationError("Boolean values are not valid schematic scalar values")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValidationError("value must be a number or non-empty CST expression")


def _vba_string(value: str) -> str:
    return value.replace('"', '""')


def _optional_xy(args: dict) -> tuple[float | None, float | None]:
    x = args.get("x")
    y = args.get("y")
    if (x is None) != (y is None):
        raise ValidationError("x and y must be provided together")
    return x, y


def _rlc_spec(kind: str) -> dict[str, str]:
    key = str(kind or "").lower()
    if key not in _RLC_SPECS:
        raise ValidationError(f"Unsupported RLC kind '{kind}'. Use resistor, inductor, or capacitor.")
    return _RLC_SPECS[key]


def _normalize_component_type(value: str) -> str:
    key = str(value or "").strip().lower().replace("-", "_")
    normalized = _COMPONENT_TYPE_ALIASES.get(key)
    if normalized is None:
        raise ValidationError(
            f"Unsupported component_type '{value}'. Use Block, ExternalPort, or Probe."
        )
    return normalized


def _normalized_ports(raw_ports: list[dict]) -> list[list[Any]]:
    if len(raw_ports) < 2:
        raise ValidationError("At least two ports are required to create a schematic net")

    ports: list[list[Any]] = []
    for index, entry in enumerate(raw_ports):
        component_type = _normalize_component_type(entry.get("component_type", ""))
        name = validate_name(str(entry.get("name", "")), f"ports[{index}].name")
        port_index = entry.get("port_index")
        if not isinstance(port_index, int):
            raise ValidationError(f"ports[{index}].port_index must be an integer")
        if port_index < 0:
            raise ValidationError(f"ports[{index}].port_index must be non-negative")
        ports.append([component_type, name, port_index])
    return ports


def _build_rlc_vba(
    *,
    name: str,
    block_type: str,
    property_name: str,
    value: str,
    unit: str,
    x: float | None,
    y: float | None,
    rotation: int | None,
) -> str:
    lines = [
        "Sub Main",
        "With Block",
        ".Reset",
        f'.Name ("{_vba_string(name)}")',
        f'.Type("{_vba_string(block_type)}")',
        f'.SetDoubleProperty ( "{_vba_string(property_name)}", "{_vba_string(value)}" )',
    ]
    if x is not None and y is not None:
        lines.append(f".Position {_format_scalar(x)}, {_format_scalar(y)}")
    if rotation is not None:
        lines.append(f".Rotate {int(rotation)}")
    lines.extend(
        [
            ".Create",
            f'.SetLocalUnitForProperty( "{_vba_string(property_name)}", "{_vba_string(unit)}" )',
            "End With",
            "End Sub",
        ]
    )
    return "\n".join(lines)


def _build_external_port_vba(
    *,
    name: str,
    x: float | None,
    y: float | None,
    number: int | None,
    impedance: str | None,
    label: str | None,
) -> str:
    lines = [
        "Sub Main",
        "With ExternalPort",
        ".Reset",
        f'.Name ("{_vba_string(name)}")',
    ]
    if number is not None:
        lines.append(f".Number {int(number)}")
    if x is not None and y is not None:
        lines.append(f".Position {_format_scalar(x)}, {_format_scalar(y)}")
    if impedance is not None:
        lines.append(f'.SetImpedance "{_vba_string(impedance)}"')
    if label:
        lines.append(f'.SetLabel "{_vba_string(label)}"')
    lines.extend([".Create", "End With", "End Sub"])
    return "\n".join(lines)


def _build_connect_vba(*, net_name: str, ports: list[list[Any]], show_label: bool) -> str:
    lines = [
        "Sub Main",
        "With Net",
        f"Dim Componentports({len(ports) - 1}, 2) As Variant",
        ".Reset",
    ]
    for index, (component_type, name, port_index) in enumerate(ports):
        lines.extend(
            [
                f'Componentports({index},0) = "{_vba_string(component_type)}"',
                f'Componentports({index},1) = "{_vba_string(name)}"',
                f"Componentports({index},2) = {int(port_index)}",
            ]
        )
    show = "True" if show_label else "False"
    lines.extend(
        [
            'GeneratedNetName = .AddComponentPorts("", Componentports, False)',
            f'.Rename GeneratedNetName, "{_vba_string(net_name)}"',
            f'.ShowNetNameLabel "{_vba_string(net_name)}", {show}',
            ".Apply",
            "End With",
            "End Sub",
        ]
    )
    return "\n".join(lines)


def _handle_create_rlc(args: dict, client: CSTClient) -> dict:
    kind = str(args.get("kind", ""))
    spec = _rlc_spec(kind)
    name = validate_name(str(args.get("name", "")))
    value = _format_scalar(args.get("value"))
    if isinstance(args.get("value"), (int, float)):
        validate_positive(float(args["value"]), "value")
    x, y = _optional_xy(args)
    rotation = args.get("rotation")
    if rotation is not None and not isinstance(rotation, int):
        raise ValidationError("rotation must be an integer")

    if client.connected:
        return client.schematic_create_rlc(
            name=name,
            block_type=spec["block_type"],
            property_name=spec["property_name"],
            value=value,
            unit=spec["unit"],
            x=x,
            y=y,
            rotation=rotation,
        )

    vba = _build_rlc_vba(
        name=name,
        block_type=spec["block_type"],
        property_name=spec["property_name"],
        value=value,
        unit=spec["unit"],
        x=x,
        y=y,
        rotation=rotation,
    )
    return {
        "status": "offline",
        "vba": vba,
        "message": "Design Studio schematic VBA generated for manual execution.",
    }


def _handle_create_external_port(args: dict, client: CSTClient) -> dict:
    name = validate_name(str(args.get("name", "")))
    x, y = _optional_xy(args)
    number = args.get("number")
    if number is not None and (not isinstance(number, int) or number < 1):
        raise ValidationError("number must be a positive integer")
    impedance = None
    if args.get("impedance") is not None:
        impedance = _format_scalar(args["impedance"])
    label = args.get("label")
    if label is not None:
        label = str(label)

    if client.connected:
        return client.schematic_create_external_port(
            name=name,
            x=x,
            y=y,
            number=number,
            impedance=impedance,
            label=label,
        )

    vba = _build_external_port_vba(
        name=name,
        x=x,
        y=y,
        number=number,
        impedance=impedance,
        label=label,
    )
    return {
        "status": "offline",
        "vba": vba,
        "message": "Design Studio external-port VBA generated for manual execution.",
    }


def _handle_connect(args: dict, client: CSTClient) -> dict:
    net_name = validate_name(str(args.get("net_name", "")), "net_name")
    ports = _normalized_ports(args.get("ports", []))
    show_label = bool(args.get("show_label", False))

    if client.connected:
        return client.schematic_connect(net_name=net_name, ports=ports, show_label=show_label)

    vba = _build_connect_vba(net_name=net_name, ports=ports, show_label=show_label)
    return {
        "status": "offline",
        "vba": vba,
        "message": "Design Studio net VBA generated for manual execution.",
    }


def _handle_list(client: CSTClient) -> dict:
    if not client.connected:
        return {
            "status": "offline",
            "message": "Schematic listing requires connected mode and an open CST project.",
        }
    return client.schematic_list()


def _handle_list_objects(client: CSTClient) -> dict:
    if not client.connected:
        return {
            "status": "offline",
            "message": "Schematic object discovery requires connected mode and an open CST project.",
        }
    return client.schematic_list_objects()


def _handle_object_methods(args: dict, client: CSTClient) -> dict:
    if not client.connected:
        return {
            "status": "offline",
            "message": "Schematic object method discovery requires connected mode.",
        }
    return client.schematic_object_methods(str(args.get("object_name", "")))


def _handle_call(args: dict, client: CSTClient) -> dict:
    if not client.connected:
        return {
            "status": "offline",
            "message": "Generic schematic calls require connected mode.",
        }
    return client.schematic_call(
        object_name=str(args.get("object_name", "")),
        method_name=str(args.get("method_name", "")),
        args=args.get("args", []),
        kwargs=args.get("kwargs", {}),
    )


async def handle(name: str, arguments: dict, client: CSTClient) -> list[TextContent]:
    try:
        if name == "cst_schematic_create_rlc":
            return _text(_handle_create_rlc(arguments, client))
        if name == "cst_schematic_create_external_port":
            return _text(_handle_create_external_port(arguments, client))
        if name == "cst_schematic_connect":
            return _text(_handle_connect(arguments, client))
        if name == "cst_schematic_list":
            return _text(_handle_list(client))
        if name == "cst_schematic_list_objects":
            return _text(_handle_list_objects(client))
        if name == "cst_schematic_object_methods":
            return _text(_handle_object_methods(arguments, client))
        if name == "cst_schematic_call":
            return _text(_handle_call(arguments, client))
        return _text({"status": "error", "message": f"Unknown schematic tool: {name}"})
    except ValidationError as e:
        return _text({"status": "error", "message": str(e)})
    except Exception as e:
        return _text({"status": "error", "message": str(e)})


def register_schematic_tools(server: Server, client: CSTClient) -> None:
    from mcp_cst_studio.tools import _registry

    _registry.add_module(TOOLS, handle, client)
