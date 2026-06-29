# CST Studio Orchestrator MCP

An open-source Model Context Protocol (MCP) server that turns CST Studio Suite into a unified AI-controllable simulation environment.

This project exposes CST Studio Suite to AI agents and automation clients. It supports 3D electromagnetic modeling, antenna and RF workflows, solver setup, result extraction, PCB/SI helpers, and direct CST Design Studio schematic control for field-circuit co-simulation through `project.schematic`.

## Highlights

- 177 MCP tools for CST automation across modeling, antennas, materials, ports, mesh, solvers, simulation, results, PCB/SI, optimization, VBA, and schematic workflows.
- Connected mode on Windows with CST Python libraries for live control of CST Studio Suite.
- Offline mode for generating CST VBA scripts when CST is not available.
- Design Studio schematic tools for RLC components, external ports, net connections, schematic inspection, object discovery, and generic RemoteObject calls.
- Generic schematic bridge for CST's runtime `project.schematic` interface, including objects such as `Block`, `Net`, `ExternalPort`, `CircuitProbe`, `SchematicLayout`, `SimulationTask`, `ParameterSweep`, and `Optimizer`.
- Built-in CST VBA reference data and guardrails for raw VBA execution.

## Why This Exists

Most CST automation examples focus on 3D Microwave Studio history commands. CST Design Studio and schematic workflows are less visible because schematic actions do not reliably appear in the 3D History List.

This fork adds a practical bridge for Design Studio:

```python
project.schematic.Block
project.schematic.Net
project.schematic.ExternalPort
project.schematic.SchematicLayout
```

On CST Studio Suite 2025.2, the generic schematic tools can enumerate 125 `project.schematic` members and call methods on runtime remote objects directly.

## Schematic Tools

Specialized tools:

- `cst_schematic_create_rlc` creates a resistor, inductor, or capacitor.
- `cst_schematic_create_external_port` creates a schematic external port.
- `cst_schematic_connect` connects block or port pins into a named net.
- `cst_schematic_list` lists schematic blocks and nets.

Generic bridge tools:

- `cst_schematic_list_objects` lists public members exposed by `project.schematic`.
- `cst_schematic_object_methods` lists methods on one schematic object.
- `cst_schematic_call` calls `project.schematic.<object_name>.<method_name>(*args, **kwargs)`.

Example generic call:

```json
{
  "object_name": "Block",
  "method_name": "GetNumberOfPorts",
  "args": []
}
```

## Installation

```bash
git clone https://github.com/guardianer9-debug/cst-studio-orchestrator-mcp.git
cd cst-studio-orchestrator-mcp
pip install -e ".[dev]"
```

## MCP Configuration

```json
{
  "mcpServers": {
    "cst-studio-orchestrator": {
      "command": "cst-studio-orchestrator-mcp",
      "env": {
        "CST_PATH": "D:\\CST2025",
        "CST_WORK_DIR": "D:\\cst_projects",
        "PYTHONPATH": "D:\\CST2025\\AMD64\\python_cst_libraries"
      }
    }
  }
}
```

The legacy command names `mcp-cst-studio` and `cst-field-circuit-mcp` are also kept for compatibility.

## Connected Mode

Connected mode requires:

- Windows
- CST Studio Suite installed
- CST Python libraries available on `PYTHONPATH`
- Python 3.10+

Example:

```powershell
$env:PYTHONPATH="D:\CST2025\AMD64\python_cst_libraries;$env:PYTHONPATH"
python -c "import cst.interface; print('CST available')"
cst-studio-orchestrator-mcp
```

## Offline Mode

When CST is unavailable, most modeling tools return VBA scripts that can be run manually in CST Studio Suite. The generic schematic reflection tools require connected mode because they depend on CST runtime remote objects.

## Development

```bash
pip install -e ".[dev]"
pytest -q
ruff check src tests
```

Current local validation:

```text
535 passed
ruff: All checks passed
```

## Project Lineage

This project is derived from `RFingAdam/mcp-cst-studio` and keeps the original AGPL-3.0-or-later license. This fork adds CST Design Studio schematic automation and a generic `project.schematic` RemoteObject bridge for broader CST Studio Suite orchestration, including antennas, RF/EM workflows, PCB/SI, and field-circuit co-simulation.

See [NOTICE](NOTICE) for attribution details.

## License

AGPL-3.0-or-later. CST Studio Suite itself is a separate commercial product from Dassault Systemes/SIMULIA and is not bundled or redistributed by this project.
