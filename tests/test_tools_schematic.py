"""Tests for Design Studio schematic tools."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def offline_client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


def _parse(result) -> dict:
    assert len(result) == 1
    return json.loads(result[0].text)


@pytest.mark.asyncio
async def test_create_resistor_offline_returns_design_studio_vba(offline_client: CSTClient):
    from mcp_cst_studio.tools.schematic import handle

    result = await handle(
        "cst_schematic_create_rlc",
        {
            "kind": "resistor",
            "name": "R1",
            "value": 50,
            "x": 10,
            "y": 20,
        },
        offline_client,
    )

    data = _parse(result)
    vba = data.get("vba", "")
    assert data["status"] == "offline"
    assert "With Block" in vba
    assert '.Name ("R1")' in vba
    assert r'.Type("CircuitBasic\Resistor")' in vba
    assert '.SetDoubleProperty ( "Resistance", "50" )' in vba
    assert '.SetLocalUnitForProperty( "Resistance", "Ohm" )' in vba
    assert ".Position 10, 20" in vba


@pytest.mark.asyncio
async def test_connect_offline_returns_net_vba(offline_client: CSTClient):
    from mcp_cst_studio.tools.schematic import handle

    result = await handle(
        "cst_schematic_connect",
        {
            "net_name": "N1",
            "ports": [
                {"component_type": "Block", "name": "R1", "port_index": 1},
                {"component_type": "Block", "name": "R2", "port_index": 0},
            ],
        },
        offline_client,
    )

    data = _parse(result)
    vba = data.get("vba", "")
    assert data["status"] == "offline"
    assert "With Net" in vba
    assert "Dim Componentports(1, 2) As Variant" in vba
    assert 'Componentports(0,0) = "Block"' in vba
    assert 'Componentports(0,1) = "R1"' in vba
    assert "Componentports(0,2) = 1" in vba
    assert '.Rename GeneratedNetName, "N1"' in vba
    assert ".Apply" in vba


@pytest.mark.asyncio
async def test_create_resistor_connected_uses_schematic_block(mock_client: CSTClient):
    from mcp_cst_studio.tools.schematic import handle

    result = await handle(
        "cst_schematic_create_rlc",
        {
            "kind": "resistor",
            "name": "R1",
            "value": 50,
            "x": 10,
            "y": 20,
        },
        mock_client,
    )

    data = _parse(result)
    assert data["status"] == "executed"
    block = mock_client._project.schematic.Block
    block.Reset.assert_called_once()
    block.Name.assert_called_once_with("R1")
    block.Type.assert_called_once_with(r"CircuitBasic\Resistor")
    block.SetDoubleProperty.assert_called_once_with("Resistance", "50")
    block.Position.assert_called_once_with(10, 20)
    block.Create.assert_called_once()
    mock_client._project.model3d.add_to_history.assert_not_called()


@pytest.mark.asyncio
async def test_connect_connected_uses_schematic_net(mock_client: CSTClient):
    from mcp_cst_studio.tools.schematic import handle

    mock_client._project.schematic.Net.AddComponentPorts.return_value = "net1"

    result = await handle(
        "cst_schematic_connect",
        {
            "net_name": "N1",
            "ports": [
                {"component_type": "Block", "name": "R1", "port_index": 1},
                {"component_type": "Block", "name": "R2", "port_index": 0},
            ],
        },
        mock_client,
    )

    data = _parse(result)
    assert data["status"] == "executed"
    net = mock_client._project.schematic.Net
    net.Reset.assert_called_once()
    net.AddComponentPorts.assert_called_once_with(
        "",
        [["Block", "R1", 1], ["Block", "R2", 0]],
        False,
    )
    net.Rename.assert_called_once_with("net1", "N1")
    net.Apply.assert_called_once()
    mock_client._project.model3d.add_to_history.assert_not_called()


@pytest.mark.asyncio
async def test_create_external_port_connected(mock_client: CSTClient):
    from mcp_cst_studio.tools.schematic import handle

    result = await handle(
        "cst_schematic_create_external_port",
        {"name": "P1", "x": 0, "y": 0, "number": 1, "impedance": 50},
        mock_client,
    )

    data = _parse(result)
    assert data["status"] == "executed"
    port = mock_client._project.schematic.ExternalPort
    port.Reset.assert_called_once()
    port.Name.assert_called_once_with("P1")
    port.Number.assert_called_once_with(1)
    port.Position.assert_called_once_with(0, 0)
    port.SetImpedance.assert_called_once_with("50")
    port.Create.assert_called_once()


class FakeBlock:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []

    def Reset(self):
        self.calls.append(("Reset", ()))

    def Name(self, value):
        self.calls.append(("Name", (value,)))
        return "ok-name"


class FakeNet:
    def Reset(self):
        return None


class FakeSchematic:
    def __init__(self) -> None:
        self.Block = FakeBlock()
        self.Net = FakeNet()


@pytest.mark.asyncio
async def test_list_schematic_objects_connected(mock_client: CSTClient):
    from mcp_cst_studio.tools.schematic import handle

    mock_client._project.schematic = FakeSchematic()

    result = await handle("cst_schematic_list_objects", {}, mock_client)

    data = _parse(result)
    assert data["status"] == "ok"
    object_names = {item["name"] for item in data["objects"]}
    assert {"Block", "Net"} <= object_names


@pytest.mark.asyncio
async def test_schematic_object_methods_connected(mock_client: CSTClient):
    from mcp_cst_studio.tools.schematic import handle

    mock_client._project.schematic = FakeSchematic()

    result = await handle(
        "cst_schematic_object_methods",
        {"object_name": "Block"},
        mock_client,
    )

    data = _parse(result)
    assert data["status"] == "ok"
    assert data["object_name"] == "Block"
    assert {"Reset", "Name"} <= set(data["methods"])


@pytest.mark.asyncio
async def test_schematic_call_invokes_arbitrary_object_method(mock_client: CSTClient):
    from mcp_cst_studio.tools.schematic import handle

    schematic = FakeSchematic()
    mock_client._project.schematic = schematic

    result = await handle(
        "cst_schematic_call",
        {"object_name": "Block", "method_name": "Name", "args": ["R1"]},
        mock_client,
    )

    data = _parse(result)
    assert data["status"] == "executed"
    assert data["result"] == "ok-name"
    assert schematic.Block.calls == [("Name", ("R1",))]


@pytest.mark.asyncio
async def test_schematic_call_rejects_private_method(mock_client: CSTClient):
    from mcp_cst_studio.tools.schematic import handle

    mock_client._project.schematic = MagicMock()

    result = await handle(
        "cst_schematic_call",
        {"object_name": "Block", "method_name": "__getattribute__", "args": []},
        mock_client,
    )

    data = _parse(result)
    assert data["status"] == "error"
    assert "public" in data["message"]
