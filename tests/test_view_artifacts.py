"""Pure artifact parsing and local HTTP boundary checks (no CST)."""
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import struct
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from mcp_cst_studio.tools.cases import read_harness, stl_bounds
from mcp_cst_studio.viewer import ArtifactHandler


def test_ascii_stl_has_real_bounds(tmp_path):
    path = tmp_path / "shape.stl"
    path.write_text("solid sample\nfacet normal 0 0 1\nouter loop\nvertex -1 2 3\nvertex 4 -5 6\nvertex 0 0 0\nendloop\nendfacet\nendsolid sample\n")
    assert stl_bounds(path) == [-1, 4, -5, 2, 0, 6]


def test_binary_stl_with_solid_header_is_still_binary(tmp_path):
    path = tmp_path / "shape.stl"
    data = b"solid misleading".ljust(80, b"\0") + struct.pack("<I", 1)
    data += struct.pack("<12fH", 0, 0, 1, -1, 2, 3, 4, -5, 6, 0, 0, 0, 0)
    path.write_bytes(data)
    assert stl_bounds(path) == [-1, 4, -5, 2, 0, 6]


def test_invalid_stl_is_not_accepted_as_geometry(tmp_path):
    path = tmp_path / "shape.stl"
    path.write_text("nothing" * 30)
    with pytest.raises(ValueError, match="no vertices"):
        stl_bounds(path)


def test_harness_preserves_units_and_topology(tmp_path):
    path = tmp_path / "harness.slh"
    path.write_text('<Harness UNITS="cm"><Knots><Knot ID="N1" X="0" Y="100" Z="20"/><Knot ID="N2" X="0" Y="-100" Z="20"/></Knots><Routes><Route ID="B"><Traces><Trace><TraceKnot ID="N1"/><TraceKnot ID="N2"/></Trace></Traces></Route></Routes><Cabling><CableInstance ID="SW_1" Length="200"/></Cabling></Harness>')
    result = read_harness(path)
    assert result["unit"] == "cm"
    assert result["routes"][0]["knots"] == ["N1", "N2"]
    assert result["knots"][0]["position"] == [0, 100, 20]


@pytest.fixture
def viewer(tmp_path):
    root = tmp_path / "runs" / "views"
    root.mkdir(parents=True)
    three = tmp_path / "three"
    three.mkdir()
    token = "a" * 32
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(ArtifactHandler, root=root, three=three, token=token))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", token, root
    server.shutdown(); server.server_close(); thread.join()


def test_viewer_requires_capability_and_rejects_traversal(viewer):
    origin, token, root = viewer
    (root.parent / "private.txt").write_text("private")
    for path, expected in [("/index.json", 404), (f"/{token}/%2e%2e/private.txt", 403)]:
        with pytest.raises(HTTPError) as error:
            urlopen(origin + path)
        assert error.value.code == expected


def test_viewer_stop_uses_same_job_receipt_and_rejects_cross_origin(viewer):
    origin, token, root = viewer
    job = root.parent / "case" / "jobs" / ("b" * 32)
    job.mkdir(parents=True)
    (job / "status.json").write_text(json.dumps({"job_id": job.name, "state": "executing"}))
    path = origin + f"/{token}/cancel/case/{job.name}"
    with pytest.raises(HTTPError) as error:
        urlopen(Request(path, method="POST", headers={"Origin": "https://unrelated.example"}))
    assert error.value.code == 403
    assert not (job / "cancel.json").exists()
    with urlopen(Request(path, method="POST", headers={"Origin": origin})) as response:
        assert json.load(response)["status"] == "requested"
    assert (job / "cancel.json").exists()
    assert json.loads((job / "status.json").read_text())["state"] == "executing"
