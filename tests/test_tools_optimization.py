"""Tests for advanced optimization tools (Phase 6)."""

from __future__ import annotations

import json

import pytest

from mcp_cst_studio.cst_client import CSTClient
from mcp_cst_studio.config import CSTConfig


@pytest.fixture
def client() -> CSTClient:
    return CSTClient(config=CSTConfig(connected=False))


@pytest.mark.asyncio
async def test_multi_objective_optimizer(client: CSTClient):
    from mcp_cst_studio.tools.parameters import handle

    result = await handle(
        "cst_multi_objective_optimizer",
        {
            "goals": [
                {
                    "result_path": "1D Results\\S-Parameters\\S1,1",
                    "goal_type": "minimize",
                    "weight": 0.7,
                },
                {
                    "result_path": "Tables\\0D Results\\Gain",
                    "goal_type": "maximize",
                    "weight": 0.3,
                },
            ],
            "parameters": [
                {"name": "patch_length", "min": 25, "max": 35},
                {"name": "patch_width", "min": 30, "max": 50},
            ],
            "method": "Genetic Algorithm",
            "max_evaluations": 150,
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("num_goals") == 2
    vba = data.get("vba", "")
    assert "Optimizer" in vba
    assert "SetGoalWeight" in vba
    assert "Genetic Algorithm" in vba


@pytest.mark.asyncio
async def test_multi_objective_with_constraints(client: CSTClient):
    from mcp_cst_studio.tools.parameters import handle

    result = await handle(
        "cst_multi_objective_optimizer",
        {
            "goals": [
                {
                    "result_path": "1D Results\\S-Parameters\\S1,1",
                    "goal_type": "minimize",
                },
            ],
            "parameters": [
                {"name": "length", "min": 10, "max": 50},
            ],
            "constraints": [
                {
                    "result_path": "Tables\\0D Results\\Gain",
                    "operator": ">",
                    "value": 5.0,
                },
            ],
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"


@pytest.mark.asyncio
async def test_multi_objective_empty_goals_error(client: CSTClient):
    from mcp_cst_studio.tools.parameters import handle

    result = await handle(
        "cst_multi_objective_optimizer",
        {
            "goals": [],
            "parameters": [{"name": "x", "min": 0, "max": 1}],
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "error"


@pytest.mark.asyncio
async def test_sensitivity_analysis(client: CSTClient):
    from mcp_cst_studio.tools.parameters import handle

    result = await handle(
        "cst_sensitivity_analysis",
        {
            "parameters": [
                {"name": "patch_length", "nominal": 30, "perturbation_pct": 5},
                {"name": "patch_width", "nominal": 40, "perturbation_pct": 10},
            ],
            "result_path": "1D Results\\S-Parameters\\S1,1",
        },
        client,
    )
    data = json.loads(result[0].text)
    assert "parameters" in data
    vba = data.get("vba", "")
    assert "ParameterSweep" in vba


@pytest.mark.asyncio
async def test_sensitivity_default_perturbation(client: CSTClient):
    from mcp_cst_studio.tools.parameters import handle

    result = await handle(
        "cst_sensitivity_analysis",
        {
            "parameters": [
                {"name": "length", "nominal": 20},
            ],
            "result_path": "1D Results\\S-Parameters\\S1,1",
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "offline"


@pytest.mark.asyncio
async def test_yield_analysis(client: CSTClient):
    from mcp_cst_studio.tools.parameters import handle

    result = await handle(
        "cst_yield_analysis",
        {
            "parameters": [
                {"name": "patch_length", "nominal": 30, "tolerance": 0.5, "distribution": "gaussian"},
                {"name": "patch_width", "nominal": 40, "tolerance": 0.3, "distribution": "uniform"},
            ],
            "pass_criteria": [
                {
                    "result_path": "1D Results\\S-Parameters\\S1,1",
                    "operator": "<",
                    "threshold": -10,
                },
            ],
            "num_samples": 100,
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("num_samples") == 100
    vba = data.get("vba", "")
    assert "ParameterSweep" in vba


@pytest.mark.asyncio
async def test_yield_analysis_empty_criteria_error(client: CSTClient):
    from mcp_cst_studio.tools.parameters import handle

    result = await handle(
        "cst_yield_analysis",
        {
            "parameters": [{"name": "x", "nominal": 1, "tolerance": 0.1}],
            "pass_criteria": [],
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "error"


@pytest.mark.asyncio
async def test_constrained_optimizer(client: CSTClient):
    from mcp_cst_studio.tools.parameters import handle

    result = await handle(
        "cst_constrained_optimizer",
        {
            "objective": {
                "result_path": "1D Results\\S-Parameters\\S1,1",
                "goal_type": "minimize",
            },
            "constraints": [
                {
                    "result_path": "Tables\\0D Results\\Gain",
                    "operator": ">",
                    "value": 8.0,
                },
                {
                    "result_path": "Tables\\0D Results\\Efficiency",
                    "operator": ">",
                    "value": 0.8,
                },
            ],
            "parameters": [
                {"name": "patch_length", "min": 25, "max": 35},
            ],
            "method": "Trust Region",
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("num_constraints") == 2
    vba = data.get("vba", "")
    assert "Optimizer" in vba
    assert "InitGoal" in vba


@pytest.mark.asyncio
async def test_constrained_optimizer_bad_bounds(client: CSTClient):
    from mcp_cst_studio.tools.parameters import handle

    result = await handle(
        "cst_constrained_optimizer",
        {
            "objective": {
                "result_path": "1D Results\\S-Parameters\\S1,1",
                "goal_type": "minimize",
            },
            "constraints": [
                {"result_path": "x", "operator": ">", "value": 0},
            ],
            "parameters": [
                {"name": "patch_length", "min": 35, "max": 25},  # inverted
            ],
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "error"


@pytest.mark.asyncio
async def test_parameter_interpolation(client: CSTClient):
    from mcp_cst_studio.tools.parameters import handle

    result = await handle(
        "cst_parameter_interpolation",
        {
            "parameter": "patch_length",
            "target_value": 30.5,
            "result_path": "1D Results\\S-Parameters\\S1,1",
        },
        client,
    )
    data = json.loads(result[0].text)
    assert data.get("parameter") == "patch_length"
    assert data.get("target_value") == 30.5
    vba = data.get("vba", "")
    assert "patch_length" in vba
