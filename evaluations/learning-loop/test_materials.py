"""Behavioral checks for bounded, read-only extraction. No network required."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

SCRIPT = Path(__file__).resolve().parents[2] / ".codex/skills/learning-loop/scripts/read_materials.py"
SPEC = importlib.util.spec_from_file_location("materials", SCRIPT)
materials = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(materials)


class MaterialReadingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="learning-loop-eval-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def text_file(self):
        path = self.root / "中文 资料.md"
        path.write_text("# 比例\n这是第二行\n第三行\n", encoding="utf-8")
        return path

    def slides(self, broken=False):
        path = self.root / "课程.pptx"
        with ZipFile(path, "w") as archive:
            archive.writestr("ppt/presentation.xml", f'<p:presentation xmlns:p="{materials.P[1:-1]}" xmlns:r="{materials.R[1:-1]}"><p:sldIdLst><p:sldId id="256" r:id="rId2"/><p:sldId id="257" r:id="rId1"/></p:sldIdLst></p:presentation>')
            archive.writestr("ppt/_rels/presentation.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="slides/slide1.xml"/><Relationship Id="rId2" Target="slides/slide2.xml"/></Relationships>')
            archive.writestr("ppt/slides/slide1.xml", "<broken" if broken else f'<p:sld xmlns:p="{materials.P[1:-1]}" xmlns:a="{materials.A[1:-1]}"><a:t>第二张</a:t></p:sld>')
            archive.writestr("ppt/slides/slide2.xml", f'<p:sld xmlns:p="{materials.P[1:-1]}" xmlns:a="{materials.A[1:-1]}"><a:t>第一张</a:t><a:t>表格文本</a:t></p:sld>')
        return path

    def test_index_does_not_claim_content_read(self):
        self.text_file()
        (self.root / "坏文件.pdf").write_bytes(b"not a PDF")
        (self.root / "photo.png").write_bytes(b"image placeholder")
        result = materials.inventory(self.root)
        self.assertEqual(len(result["files"]), 3)
        self.assertTrue(all(f["status"] == "listed_only" for f in result["files"]))
        self.assertFalse(next(f for f in result["files"] if f["path"].endswith(".png"))["supported"])

    def test_selected_text_and_source_unchanged(self):
        path = self.text_file()
        before = path.read_bytes()
        result = materials.read_units(path, "2-3")
        self.assertEqual([u["text"] for u in result["units"]], ["这是第二行", "第三行"])
        self.assertEqual(result["locator"], "line")
        self.assertFalse(result["agent_reviewed"])
        self.assertEqual(path.read_bytes(), before)

    def test_hard_text_budget_reports_truncation(self):
        result = materials.read_units(self.text_file(), "1-3", max_chars=6)
        self.assertLessEqual(sum(len(u["text"]) for u in result["units"]), 6)
        self.assertTrue(all(u["output_truncated"] for u in result["units"]))

    def test_range_validation_and_deduplication(self):
        self.assertEqual(materials.select_units("3,1-3", 5, 3), [1, 2, 3])
        for spec in ["0", "4-2", "1-10000000", "nope", "1,"]:
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                materials.select_units(spec, 5, 3)
        with self.assertRaises(ValueError):
            materials.select_units("1,2,3,4", 5, 3)

    def test_visible_slide_order_including_table_text(self):
        result = materials.read_units(self.slides(), "1-2")
        self.assertEqual(result["units"][0]["text"], "第一张\n表格文本")
        self.assertEqual(result["units"][1]["text"], "第二张")

    def test_partial_slide_failure_preserves_successful_units(self):
        result = materials.read_units(self.slides(broken=True), "1-2")
        self.assertEqual(result["units"][0]["status"], "text_extracted")
        self.assertEqual(result["units"][1]["status"], "error")

    def test_empty_text_is_not_marked_read(self):
        path = self.root / "empty.txt"
        path.write_text("", encoding="utf-8")
        result = materials.read_units(path)
        self.assertEqual(result["total_units"], 0)
        self.assertEqual(result["units"], [])
        self.assertFalse(result["agent_reviewed"])

    def test_pdf_selection_and_no_text(self):
        from pypdf import PdfWriter
        path = self.root / "pages.pdf"
        writer = PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=100, height=100)
        writer.write(path)
        result = materials.read_units(path, "2")
        self.assertEqual(result["total_units"], 3)
        self.assertEqual(result["requested_units"], [2])
        self.assertEqual(result["units"][0]["status"], "no_text")

    def test_cli_unicode_and_error_exit(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "read", str(self.text_file()), "--units", "2"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["units"][0]["text"], "这是第二行")
        failed = subprocess.run([sys.executable, str(SCRIPT), "read", str(self.root / "missing.pdf")], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(failed.returncode, 2)
        self.assertEqual(json.loads(failed.stdout)["status"], "error")


if __name__ == "__main__":
    unittest.main(verbosity=2)
