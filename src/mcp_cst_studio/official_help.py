"""Bounded, source-attributed retrieval from the installed CST HTML help.

The bundled index contains paths only, never substitute method descriptions.
HTML is parsed as data; scripts, styles and navigation indexes are not executed.
"""
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from mcp_cst_studio.config import CSTConfig


def entries() -> list[dict]:
    return json.loads((Path(__file__).parent / "data/official_help_index.json").read_text(
        encoding="utf-8"))["objects"]


class _Page(HTMLParser):
    """Extract paragraph/heading blocks, keeping official method signatures intact."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.active = None
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if self.skip:
            return
        if tag in ("p", "h1", "h2", "h3", "pre"):
            self._flush()
            self.active = (tag, dict(attrs).get("class", "").lower(), self.getpos()[0])
        elif tag == "br" and self.active:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        elif self.active and tag == self.active[0]:
            self._flush()

    def handle_data(self, data):
        if self.active and not self.skip:
            self.parts.append(data)

    def _flush(self):
        if self.active:
            tag, cls, line = self.active
            text = "".join(self.parts).replace("\xa0", " ").strip()
            if text and "index-" not in cls:
                self.blocks.append({"tag": tag, "class": cls, "line": line, "text": text})
        self.active = None
        self.parts = []


def list_objects(config: CSTConfig, category=None) -> dict:
    indexed = entries()
    categories = sorted({e["category"] for e in indexed})
    if category and category not in categories:
        return {"status": "not_found", "message": "Category not indexed", "valid_categories": categories}
    base = Path(config.cst_path) / "Online Help/mergedProjects" if config.cst_path else None
    return {"status": "ok", "source_kind": "official_local_index", "complete_catalog": False,
            "objects": [{**e, "available": bool(base and (base / e["path"]).is_file())}
                        for e in indexed if not category or e["category"] == category]}


def lookup(config: CSTConfig, args: dict) -> dict:
    name = str(args.get("object_name", "")).strip()
    domain = args.get("domain")
    matches = [e for e in entries() if e["object_name"].casefold() == name.casefold()
               and (not domain or e["domain"] == domain)]
    if not matches:
        return {"status": "not_found", "message": "Object/domain not indexed; use cst_list_vba_objects. No static-reference fallback."}
    if len(matches) > 1:
        return {"status": "ambiguous", "message": "Select the native API domain explicitly.",
                "domains": [e["domain"] for e in matches]}
    entry = matches[0]
    if not config.cst_path:
        return {"status": "unavailable", "message": "CST_PATH is not configured; local official help is required."}
    root = (Path(config.cst_path) / "Online Help/mergedProjects").resolve()
    path = (root / entry["path"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return {"status": "unavailable", "message": "Indexed official help file is missing or outside help root.", "relative_path": entry["path"]}
    if path.stat().st_size > 4_000_000:
        return {"status": "unavailable", "message": "Help page exceeds the parser size limit."}
    raw = path.read_bytes()
    # The installed pages declare their encoding; do not silently replace source characters.
    encoding = re.search(br'charset\s*=\s*["\']?([\w-]+)', raw[:4096], re.I)
    html = raw.decode(encoding.group(1).decode("ascii") if encoding else "utf-8-sig")
    parser = _Page()
    parser.feed(html)
    parser._flush()
    blocks = parser.blocks
    start = next((i for i, b in enumerate(blocks) if b["tag"] == "h1" or "heading-object" in b["class"]), None)
    if start is None:
        return {"status": "unavailable", "message": "Unsupported official page structure (missing title)."}
    blocks = blocks[start:]
    source = {"kind": "official_local_html", "path": str(path), "relative_path": entry["path"],
              "sha256": hashlib.sha256(raw).hexdigest(), "configured_cst_version": config.version,
              "version_note": "Version identifies the configured installation, not independent verification of this page's release."}
    result = {"object_name": entry["object_name"], "domain": entry["domain"], "category": entry["category"],
              "source": source, "document_title": blocks[0]["text"], "runtime_verified": False,
              "project_notes": [], "note": "Official reference only; method lookup does not verify an operation or permit solving."}
    method_blocks = [(i, b) for i, b in enumerate(blocks) if "heading-method" in b["class"]]
    def method_name(b):
        return b["text"].split("(", 1)[0].strip().casefold()
    names = list(dict.fromkeys(b["text"].split("(", 1)[0].strip() for _, b in method_blocks))
    result.update(method_names=names[:200], method_names_truncated=len(names) > 200)
    method = str(args.get("method_name", "")).strip()
    section = args.get("section", "object")
    if method and section == "example":
        return {**result, "status": "error", "message": "Use method_name or section=example, not both."}
    selected = blocks
    if method:
        selected = []
        for index, block in method_blocks:
            if method_name(block) != method.casefold():
                continue
            end = index + 1
            # DES groups several property signatures before one shared description.
            while end < len(blocks) and "heading-method" in blocks[end]["class"]:
                end += 1
            while end < len(blocks) and not any(x in blocks[end]["class"] for x in ("heading-method", "heading-category")):
                end += 1
            selected.extend(blocks[index:end])
    elif section == "example":
        selected = [b for b in blocks if "text-example" in b["class"] or b["tag"] == "pre"]
    if not selected:
        return {**result, "status": "not_found", "message": "Requested method/example not found in this official page. No generated substitute."}
    text = "\n".join(b["text"] for b in selected)
    offset = int(args.get("offset", 0))
    limit = int(args.get("max_chars", 10000))
    if offset < 0 or not 256 <= limit <= 24000:
        return {**result, "status": "error", "message": "offset must be nonnegative; max_chars must be 256..24000."}
    excerpt = text[offset:offset + limit]
    return {**result, "status": "ok", "source_line": selected[0]["line"], "section": section,
            "method_name": method or None, "excerpt": excerpt, "offset": offset,
            "total_chars": len(text), "next_offset": offset + len(excerpt) if offset + len(excerpt) < len(text) else None}
