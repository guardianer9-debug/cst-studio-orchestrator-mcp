"""Opt-in read-only audit of an installed manual. Never imports/starts a CST solver.

Set CST_HELP_TEST_PATH to the installation root. CST_HELP_AUDIT_OUTPUT can retain
the local report; it contains local paths and must not be published verbatim.
"""
import json
import os
import re
from pathlib import Path

import pytest
from mcp_cst_studio.config import CSTConfig
from mcp_cst_studio.official_help import entries, lookup


@pytest.mark.skipif(not os.environ.get("CST_HELP_TEST_PATH"), reason="Opt-in installed manual audit")
def test_installed_manual_lookup_and_pagination():
    cfg = CSTConfig(cst_path=os.environ["CST_HELP_TEST_PATH"],
                    version=os.environ.get("CST_HELP_TEST_VERSION", "unspecified"))
    report = {"pages": [], "method_queries": 0, "failures": [], "scope": "documentation only; no CST execution"}
    try:
        for entry in entries():
            args = {"object_name": entry["object_name"], "domain": entry["domain"]}
            first = lookup(cfg, args)
            assert first["status"] == "ok", first
            names = list(first["method_names"])
            offset = first["next_method_offset"]
            while offset is not None:
                page = lookup(cfg, {**args, "method_offset": offset})
                names.extend(page["method_names"])
                offset = page["next_method_offset"]
            assert len(names) == first["method_names_total"] == len(set(names))
            assert all(re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", n) for n in names)
            row = {**entry, "source": first["source"], "names": names, "warnings": first["parse_warnings"]}
            report["pages"].append(row)
            for name in names:
                response = lookup(cfg, {**args, "method_name": name, "max_chars": 24000})
                assert response["status"] == "ok", (entry, name, response)
                assert response["matched_signatures"] and response["excerpt"]
                assert response["source"]["sha256"] == first["source"]["sha256"]
                report["method_queries"] += 1
        # Independent expected names: catches omissions that a self-round-trip cannot.
        expected = {"Solid": ["GetNumberOfShapes", "GetNextFreeName", "SetMeshRefinement"],
                    "Cylinder": ["Name", "Zrange"], "DiscretePort": ["SetP1", "SetP2"],
                    "Material": ["EpsilonX", "MuZ", "AddDispEpsPole1stOrderY"],
                    "Block": ["GetNumberOfPins", "DoesExist", "SetDoubleProperty"]}
        for obj, methods in expected.items():
            for name in methods:
                assert lookup(cfg, {"object_name": obj, "method_name": name})["status"] == "ok"
        assert lookup(cfg, {"object_name": "Solid", "method_name": "SetMaterial"})["status"] == "not_found"
        refined = lookup(cfg, {"object_name": "Solid", "method_name": "SetMeshRefinement"})
        assert "volumeRefineFact" in refined["matched_signatures"][0]["signature"]
        # Query the same real long section using two page sizes, checking full reconstruction.
        texts = []
        for limit in (256, 24000):
            offset, parts = 0, []
            while offset is not None:
                response = lookup(cfg, {"object_name": "SimulationTask", "method_name": "SetProperty",
                                        "max_chars": limit, "offset": offset})
                assert response["status"] == "ok"
                parts.append(response["excerpt"])
                offset = response["next_offset"]
            texts.append("".join(parts))
        assert texts[0] == texts[1]
        report["status"] = "passed"
    except Exception as exc:
        report["status"] = "failed"
        report["failures"].append(str(exc))
        raise
    finally:
        if os.environ.get("CST_HELP_AUDIT_OUTPUT"):
            # Preserve previous attempts instead of overwriting their evidence.
            with Path(os.environ["CST_HELP_AUDIT_OUTPUT"]).open("x", encoding="utf-8") as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2)
