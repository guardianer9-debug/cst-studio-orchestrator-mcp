import json
from pathlib import Path

import pytest

from mcp_cst_studio.session_workspace import bind, copy_bundle, inventory, read_json, write_json


def test_binding_survives_restart_and_timestamp_change(tmp_path):
    first = bind(tmp_path, "stable-session", 1)
    assert bind(tmp_path, "stable-session", 999999) == first
    assert bind(tmp_path, "other-session", 1) != first
    assert not (first / "运行").exists()
    assert read_json(first / "会话信息.json")["session_id"] == "stable-session"


def test_concurrent_pi_and_desktop_binding_returns_initialized_single_directory(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    def create(_):
        path = bind(tmp_path, "shared")
        assert read_json(path / "会话信息.json")["session_id"] == "shared"
        return path
    with ThreadPoolExecutor(max_workers=6) as pool:
        roots = list(pool.map(create, range(12)))
    assert len(set(roots)) == 1


def test_copy_preserves_native_bundle_and_refuses_overwrite(tmp_path):
    source = tmp_path / "source" / "x.cst"
    source.parent.mkdir()
    source.write_bytes(b"native")
    companion = source.with_suffix("") / "Result" / "raw.bin"
    companion.parent.mkdir(parents=True)
    companion.write_bytes(b"results")
    target = tmp_path / "session" / "v001"
    receipt = copy_bundle(source, target)
    assert (target / "x/Result/raw.bin").read_bytes() == b"results"
    assert len(receipt["files"]) == 2
    with pytest.raises(FileExistsError):
        copy_bundle(source, target)
    assert source.read_bytes() == b"native"


def test_refresh_marks_external_changes_stale_without_touching_native_files(tmp_path):
    from mcp_cst_studio.session_workspace import digest
    root = bind(tmp_path, "a")
    project = root / "工程" / "native.cst"
    project.write_bytes(b"v1")
    info = read_json(root / "会话信息.json")
    info["projects"] = [{"path": str(project), "snapshot_project_sha256": digest(project)}]
    write_json(root / "会话信息.json", info)
    assert inventory(root)["projects"][0]["snapshot_current"] is True
    project.write_bytes(b"manual change")
    assert inventory(root)["projects"][0]["snapshot_current"] is False
    assert project.read_bytes() == b"manual change"
    assert not (root / "运行").exists()


def test_tampered_binding_cannot_escape_project(tmp_path):
    bind(tmp_path, "a")
    path = next((tmp_path / ".cst-sessions").glob("*.json"))
    value = read_json(path)
    value["directory"] = str(tmp_path.parent)
    write_json(path, value)
    with pytest.raises(ValueError, match="escapes"):
        bind(tmp_path, "a")


def test_native_result_changes_invalidate_curves_without_hiding_unchanged_model(tmp_path):
    from mcp_cst_studio.session_workspace import digest, results_fingerprint
    root = bind(tmp_path, "results")
    project = root / "工程" / "native.cst"
    project.write_bytes(b"same model")
    result = project.with_suffix("") / "Result" / "values.dat"
    result.parent.mkdir(parents=True)
    result.write_bytes(b"old")
    info = read_json(root / "会话信息.json")
    info["projects"] = [{"path": str(project), "snapshot_project_sha256": digest(project),
                         "snapshot_results_fingerprint": results_fingerprint(project)}]
    write_json(root / "会话信息.json", info)
    assert inventory(root)["projects"][0]["snapshot_current"]
    result.write_bytes(b"manual new run values")
    refreshed = inventory(root)["projects"][0]
    assert refreshed["snapshot_current"]
    assert not refreshed["results_current"]
