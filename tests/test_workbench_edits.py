import copy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from mcp_cst_studio.tools import workbench as wb
from mcp_cst_studio.session_workspace import digest


@pytest.fixture
def rig(tmp_path, monkeypatch):
    source = tmp_path / "original.cst"
    source.write_bytes(b"original")
    client = SimpleNamespace(_config=SimpleNamespace(session_dir=str(tmp_path)), connected=True,
                             has_project=True, project_path=str(source))
    state = {"status": "ok", "errors": {}, "parameters": {"parameters": [{"name": "L", "expression": "80"}]},
             "units": {"Time": "ns", "Frequency": "GHz"}, "frequency": {"min": 0, "max": 2.9},
             "tasks": [{"name": "Tran1", "type": "Transient", "properties": {"tmax": "250"}}],
             "schematic": {"blocks": [{"name": "RES1", "type_short": "RES"}], "nets": [{"name": "n1", "ports": [1, 2]}]},
             "block_properties": [{"name": "RES1", "properties": {"Resistance": {"type": "double", "unit": "Ohm", "value": "50"}}}]}
    monkeypatch.setattr(wb, "readback", lambda _: copy.deepcopy(state))
    def fork(*_):
        client.project_path = str(tmp_path / "version.cst")
        Path(client.project_path).write_bytes(b"copy")
    prepare = Mock(side_effect=fork)
    monkeypatch.setattr(wb, "prepare_edit", prepare)
    monkeypatch.setattr(wb, "publish_view", lambda *a, **k: {"status": "published", "errors": {}})
    def set_parameter(target, value):
        state["parameters"]["parameters"][0]["expression"] = str(value)
        return {"status": "executed"}
    client.set_parameter = Mock(side_effect=set_parameter)
    def schematic_call(**kw):
        if kw["object_name"] == "Block": state["block_properties"][0]["properties"]["Resistance"]["value"] = str(kw["args"][1])
        else: state["tasks"][0]["properties"]["tmax"] = kw["args"][1]
        return {"status": "executed"}
    client.schematic_call = Mock(side_effect=schematic_call)
    client.save_project = Mock(return_value={"status": "saved"})
    client.solver_status = Mock(return_value={"running": False})
    def execute_vba(code):
        assert ".FrequencyRange" in code and ".Start" not in code
        state["frequency"]["min"] = .01
        return {"status": "executed"}
    client.execute_vba = Mock(side_effect=execute_vba)
    args = {"kind": "load", "target": "RES1", "property": "Resistance", "value": "75", "unit": "Ohm",
            "expected_project": str(source), "expected_sha256": digest(source), "operation_id": "one"}
    return client, args, prepare, state, source


def test_load_saved_once_and_replayed_without_duplicate_version(rig):
    client, args, prepare, state, source = rig
    assert wb.edit_case(client, args)["status"] == "saved"
    assert wb.edit_case(client, args)["replayed"] is True
    assert prepare.call_count == 1
    assert client.schematic_call.call_count == 1
    assert source.read_bytes() == b"original"
    assert state["schematic"]["nets"] == [{"name": "n1", "ports": [1, 2]}]


@pytest.mark.parametrize("change", [{"unit": "kOhm"}, {"expected_sha256": "stale"}, {"target": "GND1"}])
def test_invalid_or_stale_edit_does_not_create_version(rig, change):
    client, args, prepare, _, _ = rig
    with pytest.raises(ValueError): wb.edit_case(client, {**args, **change})
    prepare.assert_not_called()


def test_retry_with_new_id_but_same_value_does_not_modify_again(rig):
    client, args, prepare, _, _ = rig
    assert wb.edit_case(client, {**args, "value": "50"})["status"] == "unchanged"
    prepare.assert_not_called()


def test_task_edit_uses_set_property_and_never_update(rig):
    client, args, _, _, _ = rig
    result = wb.edit_case(client, {**args, "kind": "task", "target": "Tran1", "property": "tmax", "unit": "ns", "value": "251"})
    assert result["status"] == "saved"
    client.schematic_call.assert_called_once_with(object_name="SimulationTask", method_name="SetProperty", args=["tmax", "251.0"], target_name="Tran1")


def test_same_operation_id_cannot_change_request(rig):
    client, args, _, _, _ = rig
    wb.edit_case(client, args)
    with pytest.raises(ValueError, match="different request"):
        wb.edit_case(client, {**args, "value": "60"})


def test_frequency_edit_uses_existing_builder_and_reads_back(rig):
    client, args, _, _, _ = rig
    assert wb.edit_case(client, {**args, "kind": "frequency", "target": "Solver", "property": "min", "unit": "GHz", "value": .01})["status"] == "saved"


def test_busy_solver_rejects_edit_before_fork(rig):
    client, args, prepare, _, _ = rig
    client.solver_status.return_value = {"running": None}
    with pytest.raises(ValueError, match="solver state"):
        wb.edit_case(client, args)
    prepare.assert_not_called()
