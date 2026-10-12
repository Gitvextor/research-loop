"""Read selected course material units as bounded JSON; never modifies sources.

Index uses only metadata. PDF needs pypdf; PPTX and UTF-8 text use the stdlib.
Extraction is not proof that an agent inspected the returned content.
"""

import argparse
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile

SUPPORTED = {".pdf", ".pptx", ".md", ".txt"}
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def source_info(path):
    stat = path.stat()
    return {"path": str(path), "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def inventory(root):
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("index requires a directory")
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            info = source_info(path)
            info.update(relative_path=str(path.relative_to(root)),
                        supported=path.suffix.lower() in SUPPORTED,
                        status="listed_only")
            files.append(info)
    return {"root": str(root), "status": "listed_only", "files": files}


def select_units(spec, total, limit):
    if limit < 1:
        raise ValueError("max-units must be positive")
    if total == 0 and spec is None:
        return []
    selected = set()
    for part in (spec or "1").split(","):
        match = re.fullmatch(r"\s*(\d+)(?:-(\d+))?\s*", part)
        if not match:
            raise ValueError("units must look like 1,3-5 (one-based)")
        first = int(match[1])
        last = int(match[2] or match[1])
        if not 1 <= first <= last <= total:
            raise ValueError(f"unit range {first}-{last} is outside 1-{total}")
        if last - first + 1 > limit:
            raise ValueError(f"request exceeds max-units={limit}; read smaller batches")
        selected.update(range(first, last + 1))
        if len(selected) > limit:
            raise ValueError(f"request exceeds max-units={limit}; read smaller batches")
    return sorted(selected)


def pptx_order(archive):
    # Presentation relationship order, not filename order, is the visible order.
    from posixpath import normpath
    rels = ET.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))
    targets = {rel.get("Id"): rel.get("Target") for rel in rels
               if rel.get("TargetMode") != "External"}
    presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
    names = []
    for slide in presentation.findall(f"{P}sldIdLst/{P}sldId"):
        target = targets[slide.get(f"{R}id")]
        name = normpath(target.lstrip("/") if target.startswith("/") else "ppt/" + target)
        if not name.startswith("ppt/slides/"):
            raise ValueError("unexpected PPTX slide relationship")
        names.append(name)
    return names


def read_units(path, spec=None, max_units=12, max_chars=12000):
    path = path.resolve(strict=True)
    if not path.is_file():
        raise ValueError("read requires a file")
    if max_chars < 1:
        raise ValueError("max-chars must be positive")
    suffix = path.suffix.lower()
    info = source_info(path)
    archive = None
    pdf_stream = None
    try:
        if suffix == ".pdf":
            from pypdf import PdfReader
            pdf_stream = path.open("rb")
            reader = PdfReader(pdf_stream)
            if reader.is_encrypted and not reader.decrypt(""):
                raise ValueError("PDF is encrypted; a readable copy is needed")
            total, kind = len(reader.pages), "pdf_page"
            extract = lambda n: reader.pages[n - 1].extract_text() or ""
        elif suffix == ".pptx":
            archive = ZipFile(path)
            names = pptx_order(archive)
            total, kind = len(names), "slide"

            def extract(n):
                xml = ET.fromstring(archive.read(names[n - 1]))
                return "\n".join("".join(node.itertext()) for node in xml.iter(f"{A}t"))

        elif suffix in {".md", ".txt"}:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
            total, kind = len(lines), "line"
            extract = lambda n: lines[n - 1]
        else:
            raise ValueError(f"unsupported file type: {suffix}")
        selected = select_units(spec, total, max_units)
        # Reserve a fair text budget for every requested unit.
        per_unit = max_chars // len(selected) if selected else 0
        units = []
        for number in selected:
            try:
                text = extract(number)
                units.append({"unit": number,
                              "status": "text_extracted" if text.strip() else "no_text",
                              "extracted_chars": len(text),
                              "output_truncated": len(text) > per_unit,
                              "text": text[:per_unit]})
            except Exception as exc:
                units.append({"unit": number, "status": "error",
                              "error": f"{type(exc).__name__}: {exc}"})
        return {"source": info, "locator": kind, "total_units": total,
                "requested_units": selected, "units": units,
                "agent_reviewed": False,
                "notice": "Text extraction only. Check diagrams/tables visually when needed; no_text does not mean an empty page."}
    finally:
        if archive:
            archive.close()
        if pdf_stream:
            pdf_stream.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    index = commands.add_parser("index", help="List files and metadata without reading content")
    index.add_argument("path", type=Path)
    read = commands.add_parser("read", help="Extract selected PDF pages, slides or text lines")
    read.add_argument("path", type=Path)
    read.add_argument("--units", help="One-based units, e.g. 1,3-5; default: 1")
    read.add_argument("--max-units", type=int, default=12)
    read.add_argument("--max-chars", type=int, default=12000)
    args = parser.parse_args(argv)
    try:
        if args.command == "index":
            result = inventory(args.path)
        else:
            result = read_units(args.path, args.units, args.max_units, args.max_chars)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if any(unit["status"] == "error" for unit in result.get("units", [])) else 0
    except Exception as exc:
        print(json.dumps({"status": "error", "path": str(args.path),
                          "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
