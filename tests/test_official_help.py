"""Synthetic HTML fixtures; no redistributed CST manual text or installation needed."""
import hashlib
import pytest
from mcp_cst_studio.config import CSTConfig
from mcp_cst_studio import official_help as help


@pytest.fixture
def page(tmp_path):
    e = next(e for e in help.entries() if e["object_name"] == "Solid")
    p = tmp_path / "Online Help/mergedProjects" / e["path"]
    p.parent.mkdir(parents=True)
    p.write_text('''<meta charset="utf-8"><script>secret_script_text()</script>
<h1>Solid Object</h1><p>Synthetic overview.</p>
<p class="VBA-Index-Category">Navigation must be omitted</p>
<p class="VBA-Heading-Category">Methods</p>
<p class="VBA-Heading-Method">ChangeMaterial ( <a>string</a> shape, string material )</p>
<p class="VBA-Text-Indent">Synthetic change description &amp; condition.</p>
<p class="VBA-Heading-Method">Reset</p><p>Reset description.</p>
<p class="VBA-Heading-Category">Example</p>
<p class="VBA-Text-Example">With Solid</p>
<p class="VBA-Text-Example">  .ChangeMaterial "demo:shape", "PEC"</p>
<p class="VBA-Text-Example">End With</p>''', encoding="utf-8")
    return CSTConfig(cst_path=str(tmp_path), version="2025"), p


def test_exact_official_method_and_provenance(page):
    config, path = page
    result = help.lookup(config, {"object_name": "solid", "method_name": "changematerial"})
    assert result["status"] == "ok"
    assert "string shape" in result["excerpt"]
    assert "& condition" in result["excerpt"]
    assert "Reset description" not in result["excerpt"]
    assert "secret_script" not in result["excerpt"]
    assert result["source"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result["source"]["configured_cst_version"] == "2025"
    assert result["runtime_verified"] is False
    assert result["project_notes"] == []


def test_wrong_method_never_uses_legacy_reference(page):
    config, _ = page
    result = help.lookup(config, {"object_name": "Solid", "method_name": "SetMaterial"})
    assert result["status"] == "not_found"
    assert "excerpt" not in result
    assert "ChangeMaterial" in result["method_names"]


def test_examples_are_extracted_not_synthesized(page):
    config, _ = page
    result = help.lookup(config, {"object_name": "Solid", "section": "example"})
    assert result["excerpt"] == 'With Solid\n.ChangeMaterial "demo:shape", "PEC"\nEnd With'
    assert '"value"' not in result["excerpt"]


def test_missing_install_or_file_is_explicit(page):
    config, path = page
    assert help.lookup(CSTConfig(), {"object_name": "Solid"})["status"] == "unavailable"
    path.unlink()
    assert help.lookup(config, {"object_name": "Solid"})["status"] == "unavailable"
    assert not next(e for e in help.list_objects(config)["objects"] if e["object_name"] == "Solid")["available"]


def test_ambiguous_domains_and_unknown_names(page):
    config, _ = page
    assert help.lookup(config, {"object_name": "Units"})["status"] == "ambiguous"
    assert help.lookup(config, {"object_name": "../Solid"})["status"] == "not_found"
    assert help.lookup(config, {"object_name": "Solid", "domain": "schematic"})["status"] == "not_found"


def test_paginated_text_is_lossless_and_updates_have_new_hash(page):
    config, path = page
    path.write_text('<h1>Solid</h1><p>' + 'abcd ' * 500 + '</p>', encoding="utf-8")
    whole = help.lookup(config, {"object_name": "Solid"})
    chunks, offset = [], 0
    while offset is not None:
        result = help.lookup(config, {"object_name": "Solid", "offset": offset, "max_chars": 256})
        assert len(result["excerpt"]) <= 256
        chunks.append(result["excerpt"])
        offset = result["next_offset"]
    assert "".join(chunks) == whole["excerpt"]
    path.write_text('<h1>Solid</h1><p>changed</p>', encoding="utf-8")
    assert help.lookup(config, {"object_name": "Solid"})["source"]["sha256"] != whole["source"]["sha256"]


def test_index_cannot_escape_help_root(page, monkeypatch):
    config, _ = page
    monkeypatch.setattr(help, "entries", lambda: [{"object_name": "Solid", "path": "../../escape.htm", "domain": "3d", "category": "geometry"}])
    assert help.lookup(config, {"object_name": "Solid"})["status"] == "unavailable"


def test_material_assignment_is_classified_as_model_edit():
    from mcp_cst_studio.operation_policy import is_model_edit
    assert is_model_edit("cst_assign_material", {})
    assert not is_model_edit("cst_vba_help", {})


@pytest.mark.parametrize("title", ['<h1>Solid Object</h1>', '<p class="VBA-Heading-Object">Solid Object</p>'])
def test_native_title_variants(page, title):
    config, path = page
    path.write_text(title + '<p class="VBA-Heading-Method">Reset</p><p>description</p>', encoding="utf-8")
    assert help.lookup(config, {"object_name": "Solid", "method_name": "Reset"})["status"] == "ok"


def test_shared_property_description_is_not_lost(page):
    config, path = page
    path.write_text('<h1>Solid</h1><p class="VBA-Heading-Method">SetA (string x)</p><p class="VBA-Heading-Method">SetB (double x)</p><p>Shared property conditions.</p><p class="VBA-Heading-Method">Reset</p>', encoding="utf-8")
    r = help.lookup(config, {"object_name": "Solid", "method_name": "SetA"})
    assert "Shared property conditions" in r["excerpt"]



def test_explicit_save_ends_version_editing_interval(mock_client, tmp_path):
    mock_client._config.work_dir = str(tmp_path)
    mock_client._project_path = str(tmp_path / "checkpoint.cst")
    mock_client._edit_branch = mock_client._project_path
    result = mock_client.save_project()
    assert result["status"] == "saved"
    assert mock_client._edit_branch is None


@pytest.mark.asyncio
async def test_help_remains_readable_when_project_is_stale_or_task_owned(page, monkeypatch):
    import json
    from mcp.server import Server
    from mcp_cst_studio.cst_client import CSTClient
    from mcp_cst_studio.tools import ToolRegistry
    from mcp_cst_studio.tools import vba
    from mcp_cst_studio import operation_policy
    config, _ = page
    client = CSTClient(config)
    client._task_job = {"state": "running"}
    def stale(_client):
        raise ValueError("Native file changed")
    monkeypatch.setattr(operation_policy, "check_external_change", stale)
    registry = ToolRegistry()
    registry.add_module(vba.TOOLS, vba.handle, client)
    registry.install(Server("help-test"))
    result = await registry.invoke("cst_vba_help", {"object_name": "Solid"})
    assert not result.isError
    assert json.loads(result.content[0].text)["status"] == "ok"
