"""Regression checks for conservative PDF geometry candidates.

Run with an interpreter providing pdfplumber and PyMuPDF:
    python -m unittest discover -s scripts -p test_pdf_overlap_checker.py -v
No package installation, network, or persistent fixture files are needed.
"""
import builtins
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("pdf-overlap-checker.py")
SPEC = importlib.util.spec_from_file_location("pdf_overlap_checker_under_test", SCRIPT)
checker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checker
SPEC.loader.exec_module(checker)
BBox, Segment = checker.BBox, checker.Segment


class CandidateTests(unittest.TestCase):
    def test_word_overlap_is_retained_without_claiming_ink_collision(self):
        words = [BBox(10, 10, 40, 25, "liminf"), BBox(15, 22, 30, 29, "p→∞")]
        issues = checker.check_word_overlaps(words)
        overlaps = [i for i in issues if i.category == "text-overlap"]
        self.assertEqual(len(overlaps), 1)
        self.assertEqual(overlaps[0].level, "WARN")
        self.assertTrue(overlaps[0].candidate)
        self.assertEqual(overlaps[0].review_status, "needs-visual-review")
        self.assertEqual(overlaps[0].bbox, [10, 10, 40, 29])

    def test_distinct_text_on_identical_boxes_is_not_suppressed(self):
        issues = checker.check_word_overlaps(
            [BBox(10, 10, 40, 25, "ALPHA"), BBox(10, 10, 40, 25, "BETA")])
        self.assertTrue(any(i.category == "text-overlap" for i in issues))

    def test_repeated_labels_at_different_locations_keep_both_findings(self):
        words = [BBox(x, 10, x+20, 25, label)
                 for base in (10, 200)
                 for x, label in ((base, "A"), (base+5, "B"))]
        self.assertEqual(sum(i.category == "text-overlap"
                             for i in checker.check_word_overlaps(words)), 2)

    def test_wide_nodes_overlap_and_through_lines_are_detected(self):
        a, b = BBox(50, 50, 300, 100), BBox(250, 70, 500, 120)
        overlaps = checker.check_node_overlap([a, b], [1, 2])
        self.assertEqual(len(overlaps), 1)
        self.assertEqual(overlaps[0].level, "ERROR")
        self.assertIsNotNone(overlaps[0].bbox)
        hits = checker.check_line_through_nodes([Segment(0, 80, 350, 80)], [a], [1])
        self.assertTrue(any(i.category == "line-through-node" for i in hits))

    def test_four_crossings_are_not_silently_discarded(self):
        lines = [Segment(0, y, 350, y, path_id=100+i)
                 for i, y in enumerate((60, 70, 80, 90))]
        self.assertEqual(len(checker.check_line_through_nodes(
            lines, [BBox(50, 50, 300, 100)], [1])), 4)

    def test_nested_background_is_excluded_but_wide_child_retained(self):
        boxes = [BBox(0, 0, 550, 180), BBox(50, 50, 300, 100)]
        self.assertEqual(checker.candidate_node_indices(boxes), [1])

    def test_report_preserves_all_candidates_and_local_groups(self):
        issues = [checker.Issue("WARN", "text-tight", str(i), page=2,
                                bbox=[10, 10, 30, 30]) for i in range(99)]
        report = checker.build_report("fixture.pdf", issues, [{"page": 2}])
        self.assertEqual(len(report["warnings"]), 99)
        self.assertEqual(report["summary"]["warning_count"], 99)
        self.assertEqual(report["summary"]["review_group_count"], 1)
        self.assertEqual(report["review_groups"][0]["count"], 99)
        self.assertEqual(report["status"], "needs-visual-review")

    def test_missing_fitz_is_incomplete_and_nonzero_even_in_json_mode(self):
        original_import = builtins.__import__

        def without_fitz(name, *args, **kwargs):
            if name == "fitz":
                raise ImportError("simulated missing fitz")
            return original_import(name, *args, **kwargs)

        output = io.StringIO()
        with patch("builtins.__import__", side_effect=without_fitz), contextlib.redirect_stdout(output):
            code = checker.main(["fixture.pdf", "--json"])
        report = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "incomplete")
        self.assertFalse(report["coverage"]["complete"])
        self.assertEqual(report["errors"][0]["review_status"], "not-run")
        self.assertNotIn("PASS", output.getvalue())

    def test_missing_pdfplumber_is_incomplete_and_nonzero(self):
        original_import = builtins.__import__

        def without_pdfplumber(name, *args, **kwargs):
            if name == "pdfplumber":
                raise ImportError("simulated missing pdfplumber")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=without_pdfplumber):
            with self.assertRaises(checker.IncompleteCheck):
                checker._validate_pdf_page("fixture.pdf")

    def test_console_examples_are_limited_without_losing_json_findings(self):
        issues = [checker.Issue("WARN", "text-tight", str(i), page=1,
                                bbox=[10, 10, 30, 30]) for i in range(99)]
        output = io.StringIO()
        with patch.object(checker, "validate_pdf", return_value=issues), contextlib.redirect_stdout(output):
            code = checker.main(["fixture.pdf", "--max-per-category", "3"])
        self.assertEqual(code, 1)
        self.assertEqual(output.getvalue().count("needs-visual-review; page="), 3)
        self.assertIn("96", output.getvalue())


class GeneratedPDFTests(unittest.TestCase):
    def test_stroke_only_node_is_not_hidden_by_small_filled_decoration(self):
        import fitz
        with tempfile.TemporaryDirectory(prefix="pdf-stroke-node-") as directory:
            for native in (True, False):
                for decoration in (False, True):
                    with self.subTest(native=native, decoration=decoration):
                        path = Path(directory) / f"stroke-{native}-{decoration}.pdf"
                        with fitz.open() as doc:
                            page = doc.new_page(width=400, height=200)
                            if native:
                                xref = doc.get_new_xref()
                                doc.update_object(xref, "<<>>")
                                stream = b"q 0 0 0 RG 1 w 50 100 250 50 re S 100 130 m 250 130 l S "
                                if decoration:
                                    stream += b"10 185 5 5 re f "
                                doc.update_stream(xref, stream + b"Q")
                                page.set_contents(xref)
                            else:
                                page.draw_rect(fitz.Rect(50, 50, 300, 100), fill=None)
                                page.draw_line(fitz.Point(100, 70), fitz.Point(250, 70))
                                if decoration:
                                    page.draw_rect(fitz.Rect(10, 10, 15, 15), fill=(0, 0, 0))
                            doc.save(path)
                        coverage = []
                        issues = checker.validate_pdf(str(path), coverage)
                        hits = [i for i in issues if i.category == "line-through-node"]
                        self.assertTrue(hits, (native, decoration, coverage))
                        self.assertGreaterEqual(coverage[0]["node_candidate_count"], 1)
                        self.assertTrue(any(b["path_id"] >= 0
                                            for i in hits for b in i.related_bboxes))

    def test_later_page_failure_retains_completed_page_findings(self):
        import fitz
        with tempfile.TemporaryDirectory(prefix="pdf-partial-check-") as directory:
            path = Path(directory) / "two-pages.pdf"
            with fitz.open() as doc:
                doc.new_page()
                doc.new_page()
                doc.save(path)

            def page_check(_path, page_index, coverage):
                if page_index == 1:
                    raise checker.IncompleteCheck("simulated page 2 failure")
                coverage.append({"page": 1})
                return [checker.Issue("WARN", "text-overlap", "retained page 1 finding",
                                      page=1, bbox=[10, 10, 30, 30])]

            output = io.StringIO()
            with patch.object(checker, "_validate_pdf_page", side_effect=page_check), contextlib.redirect_stdout(output):
                code = checker.main([str(path), "--json"])
            report = json.loads(output.getvalue())
            self.assertEqual(code, 2)
            self.assertEqual(report["status"], "incomplete")
            self.assertFalse(report["coverage"]["complete"])
            self.assertEqual(report["coverage"]["pages_checked"], 1)
            self.assertEqual(report["coverage"]["uncompleted_pages"], [2])
            self.assertEqual(report["warnings"][0]["message"], "retained page 1 finding")
            self.assertEqual(report["errors"][0]["page"], 2)

    def test_second_page_real_defects_and_wide_boxes_are_detected(self):
        import fitz
        # Import now so a missing geometry dependency fails the test explicitly.
        import pdfplumber  # noqa: F401
        with tempfile.TemporaryDirectory(prefix="pdf-overlap-regression-") as directory:
            path = Path(directory) / "two-page-defects.pdf"
            with fitz.open() as doc:
                doc.new_page(width=600, height=400)
                page = doc.new_page(width=600, height=400)
                page.draw_rect(fitz.Rect(50, 50, 300, 100), fill=(1, .9, .9))
                page.draw_rect(fitz.Rect(250, 70, 500, 120), fill=(.9, 1, .9))
                page.draw_line(fitz.Point(0, 80), fitz.Point(350, 80))
                page.insert_text(fitz.Point(70, 180), "ALPHA", fontsize=14)
                page.draw_line(fitz.Point(60, 176), fitz.Point(150, 176))
                page.insert_text(fitz.Point(70, 240), "ALPHA", fontsize=16)
                page.insert_text(fitz.Point(90, 249), "BETA", fontsize=16)
                doc.save(path)
            coverage = []
            issues = checker.validate_pdf(str(path), coverage)
            self.assertEqual(len(coverage), 2)
            categories = {i.category for i in issues if i.page == 2}
            self.assertTrue({"node-overlap", "line-through-node", "text-line", "text-overlap"} <= categories,
                            categories)
            self.assertTrue(all(i.bbox for i in issues))
            self.assertTrue(all(i.page == 2 for i in issues))


if __name__ == "__main__":
    unittest.main()
