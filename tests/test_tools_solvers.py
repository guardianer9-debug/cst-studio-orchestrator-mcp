"""Tests for solver configuration tools."""
from __future__ import annotations

import json

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


@pytest.mark.asyncio
async def test_configure_time_domain_solver(client: CSTClient):
    from mcp_cst_studio.tools.solvers import handle

    result = await handle(
        "cst_configure_time_domain_solver",
        {
            "accuracy": -40,
            "max_time_steps": 0,
            "stimulation_port": 1,
        },
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "Solver" in vba
    assert data.get("status") == "offline"
    assert data.get("solver") == "Time Domain"
    assert data.get("accuracy_db") == -40


@pytest.mark.asyncio
async def test_configure_frequency_domain_solver(client: CSTClient):
    from mcp_cst_studio.tools.solvers import handle

    result = await handle(
        "cst_configure_frequency_domain_solver",
        {
            "accuracy": 1e-6,
            "f_min": 1.0,
            "f_max": 5.0,
            "samples": 1001,
        },
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "FDSolver" in vba
    assert data.get("status") == "offline"
    assert data.get("solver") == "Frequency Domain"
    assert data.get("f_min_ghz") == 1.0
    assert data.get("f_max_ghz") == 5.0


@pytest.mark.asyncio
async def test_configure_eigenmode_solver(client: CSTClient):
    from mcp_cst_studio.tools.solvers import handle

    result = await handle(
        "cst_configure_eigenmode_solver",
        {"number_of_modes": 3},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert "EigenmodeSolver" in vba
    assert data.get("status") == "offline"
    assert data.get("solver") == "Eigenmode"
    assert data.get("number_of_modes") == 3


@pytest.mark.asyncio
async def test_get_solver_info(client: CSTClient):
    from mcp_cst_studio.tools.solvers import handle

    result = await handle("cst_get_solver_info", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert "status" in data
    assert data.get("status") == "offline"


@pytest.mark.asyncio
async def test_define_user_excitation_signal_returns_usf_and_timesignal_vba(client: CSTClient):
    from mcp_cst_studio.tools.solvers import handle

    hpm_usf = """
Function ExcitationFunction(t As Double) As Double
    If(t<10) Then
        ExcitationFunction = 5000*t*Sin(2*pi*2.5*t)
    ElseIf(t<60) Then
        ExcitationFunction = 50000*Sin(2*pi*2.5*t)
    ElseIf(t<70) Then
        ExcitationFunction = 50000*(7-0.1*t)*Sin(2*pi*2.5*t)
    Else
        ExcitationFunction = 0
    End If
End Function
""".strip()

    result = await handle(
        "cst_define_user_excitation_signal",
        {
            "name": "signal1",
            "usf_code": hpm_usf,
            "ttotal": 80,
            "min_samples": 1000,
            "set_as_reference": True,
        },
        client,
    )

    assert len(result) == 1
    data = json.loads(result[0].text)
    vba = data.get("vba", "")
    assert data.get("status") == "offline"
    assert data.get("signal_name") == "signal1"
    assert data.get("usf_filename") == "signal1.usf"
    assert data.get("usf_code") == hpm_usf
    assert 'With TimeSignal' in vba
    assert '.Name "signal1"' in vba
    assert '.SignalType "User"' in vba
    assert '.ProblemType "High Frequency"' in vba
    assert '.Ttotal "80"' in vba
    assert '.MinUserSignalSamples "1000"' in vba
    assert '.Create' in vba
    assert '.ExcitationSignalAsReference "signal1", "High Frequency"' in vba
    assert data.get("write_location_hint") == r"Model\3D\signal1.usf"


@pytest.mark.asyncio
async def test_define_user_excitation_signal_requires_excitation_function(client: CSTClient):
    from mcp_cst_studio.tools.solvers import handle

    result = await handle(
        "cst_define_user_excitation_signal",
        {
            "name": "signal1",
            "usf_code": "Function OtherFunction(t As Double) As Double\nEnd Function",
        },
        client,
    )

    data = json.loads(result[0].text)
    assert data.get("status") == "error"
    assert "ExcitationFunction" in data.get("message", "")


@pytest.mark.asyncio
async def test_define_user_excitation_signal_rejects_real_main_program(client: CSTClient):
    from mcp_cst_studio.tools.solvers import handle

    result = await handle(
        "cst_define_user_excitation_signal",
        {
            "name": "signal1",
            "usf_code": (
                "Function ExcitationFunction(t As Double) As Double\n"
                "ExcitationFunction = 0\n"
                "End Function\n"
                "Sub Main()\n"
                "End Sub"
            ),
        },
        client,
    )

    data = json.loads(result[0].text)
    assert data.get("status") == "error"
    assert "Sub Main" in data.get("message", "")


@pytest.mark.asyncio
async def test_frequency_domain_f_min_gte_f_max_returns_error(client: CSTClient):
    from mcp_cst_studio.tools.solvers import handle

    result = await handle(
        "cst_configure_frequency_domain_solver",
        {"f_min": 5.0, "f_max": 1.0},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
    assert "message" in data


@pytest.mark.asyncio
async def test_frequency_domain_f_min_equal_f_max_returns_error(client: CSTClient):
    from mcp_cst_studio.tools.solvers import handle

    result = await handle(
        "cst_configure_frequency_domain_solver",
        {"f_min": 3.0, "f_max": 3.0},
        client,
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
    assert "message" in data


@pytest.mark.asyncio
async def test_unknown_tool_returns_error(client: CSTClient):
    from mcp_cst_studio.tools.solvers import handle

    result = await handle("cst_nonexistent_solver_tool", {}, client)
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data.get("status") == "error"
    assert "message" in data
