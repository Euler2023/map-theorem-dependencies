"""Behavior regressions for the validator's documented literal subset."""

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
SCRIPT = Path(__file__).with_name("tikz-validator.py")
spec = importlib.util.spec_from_file_location("tikz_validator", SCRIPT)
v = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = v
spec.loader.exec_module(v)


def node(name, x, y, opts="minimum width=1cm,minimum height=1cm", body="A"):
    return rf"\node[{opts}] ({name}) at ({x},{y}) {{{body}}};"


def categories(content):
    return [issue.category for issue in v.validate_content(content)]


class LiteralGeometry(unittest.TestCase):
    def test_leading_decimal_and_signs(self):
        points = v.parse_draw_coords(r"\draw (.7,-.5)--(+.8,+2.);")
        self.assertEqual([(p.x, p.y) for p in points], [(.7, -.5), (.8, 2.)])
        self.assertAlmostEqual(v.parse_nodes([node("a", ".7", "-.5")])[0].x, .7)

    def test_physical_scalar_bases_prevent_false_collision(self):
        text = r"\begin{tikzpicture}[x=2cm,y=10mm]" + node("a", 0, 0) + node("b", .8, 0) + r"\end{tikzpicture}"
        self.assertAlmostEqual(v.parse_scene(text).nodes[1].x, 1.6)
        self.assertNotIn("collision", categories(text))

    def test_negative_basis_and_dimensions_have_different_units(self):
        text = r"\begin{tikzpicture}[x=10mm,y=-2cm]" + node("a", 1, 2, "minimum width=20mm,minimum height=1cm") + r"\end{tikzpicture}"
        n = v.parse_scene(text).nodes[0]
        self.assertEqual((n.x, n.y, n.width, n.height), (1, -4, 2, 1))

    def test_scope_basis_is_restored(self):
        text = r"\begin{tikzpicture}[x=2cm]\begin{scope}[x=3cm]" + node("a", 1, 0) + r"\end{scope}" + node("b", 1, 3) + r"\end{tikzpicture}"
        self.assertEqual([n.x for n in v.parse_scene(text).nodes], [3, 2])

    def test_distinct_pictures_do_not_collide(self):
        text = "".join(r"\begin{tikzpicture}" + node(n, 0, 0) + r"\end{tikzpicture}" for n in ["a", "b"])
        self.assertNotIn("collision", categories(text))

    def test_unsupported_transform_warns_and_skips_geometry(self):
        for opts in ["scale=2", "rotate=30", "xshift=2cm", "x={(2cm,1cm)}", "x=\\unit", "mystyle"]:
            with self.subTest(opts=opts):
                text = r"\begin{tikzpicture}[" + opts + "]" + node("a", 0, 0) + node("b", .2, 0) + r"\end{tikzpicture}"
                self.assertIn("coverage", categories(text))
                self.assertNotIn("collision", categories(text))

    def test_unknown_node_style_not_silently_defaulted(self):
        text = node("a", 0, 0, "box,minimum width=1cm,minimum height=1cm") + node("b", .2, 0)
        self.assertIn("coverage", categories(text))
        self.assertNotIn("collision", categories(text))

    def test_global_tikzset_geometry_is_not_ignored(self):
        for setting in ["x=2cm", "every node/.style={minimum width=3cm}"]:
            text = r"\tikzset{" + setting + r"}\begin{tikzpicture}" + node("a", 0, 0) + node("b", .2, 0) + r"\end{tikzpicture}"
            self.assertIn("coverage", categories(text))
            self.assertNotIn("collision", categories(text))

    def test_legacy_every_node_style_cannot_silently_pass(self):
        text = r"\tikzstyle{every node}=[scale=2,transform shape]" + node("a", 0, 0) + node("b", 1.5, 0)
        self.assertIn("coverage", categories(text))
        self.assertNotIn("collision", categories(text))
        self.assertTrue(all(not n.geometry_ok for n in v.parse_scene(text).nodes))

    def test_pgf_transform_scale_cannot_silently_pass(self):
        text = r"\pgftransformscale{2}" + node("a", 0, 0) + node("b", 1.5, 0)
        self.assertIn("coverage", categories(text))
        self.assertNotIn("collision", categories(text))
        self.assertTrue(all(not n.geometry_ok for n in v.parse_scene(text).nodes))

    def test_macro_size_and_nonliteral_position_warn(self):
        self.assertIn("coverage", categories(node("a", 0, 0, r"minimum width=\W,minimum height=1cm")))
        self.assertIn("coverage", categories(r"\node[minimum width=1cm] (a) at ($(b)+(1,0)$) {A};"))

    def test_multiline_command_and_body_cannot_silently_pass(self):
        text = "\\node[minimum width=2cm,minimum height=.4cm] (a) at (0,0)\n" + r"{A\\B\\C\\D};"
        scene = v.parse_scene(text)
        self.assertEqual(len(scene.nodes), 1)
        self.assertGreater(scene.nodes[0].height, 1.8)
        self.assertIn("node-metrics", categories(text))

    def test_multiline_height_finds_previously_missed_overlap(self):
        text = node("a", 0, 0, "minimum width=2cm,minimum height=.4cm", r"A\\B\\C\\D") + node("b", 0, 1.25, "minimum width=2cm,minimum height=.4cm")
        self.assertIn("collision", categories(text))

    def test_minimum_boxes_overlap_including_same_center(self):
        for x in [0, .5]:
            with self.subTest(x=x):
                self.assertIn("collision", categories(node("a", 0, 0) + node("b", x, 0)))

    def test_cardinal_anchor_offsets_center(self):
        n = v.parse_nodes([node("a", 1, 2, "minimum width=2cm,minimum height=1cm,anchor=north west")])[0]
        self.assertEqual((n.x, n.y), (2, 1.5))

    def test_rectangle_units_follow_axes(self):
        text = r"\begin{tikzpicture}[x=2cm,y=10mm]\fill[fill=gray] (.2,.3) rectangle (2.2,3.3);\end{tikzpicture}"
        z = v.parse_scene(text).zones[0]
        self.assertAlmostEqual(z.x_min, .4)
        self.assertAlmostEqual(z.x_max, 4.4)
        self.assertAlmostEqual(z.y_max, 3.3)

    def test_transformed_rectangle_not_used_as_cm_container(self):
        text = r"\fill[xshift=20cm] (0,0) rectangle (2,2);" + node("a", 1, 1)
        self.assertIn("coverage", categories(text))
        self.assertEqual(v.parse_scene(text).zones, [])

    def test_comments_are_not_nodes(self):
        self.assertEqual(v.parse_scene("% " + node("a", 0, 0)).nodes, [])

    def test_escaped_percent_does_not_hide_later_comment(self):
        text = r"\% still text % " + node("a", 0, 0)
        self.assertEqual(v.parse_scene(text).nodes, [])


class LegalRoutes(unittest.TestCase):
    def test_diagonal_is_legal_by_default(self):
        self.assertEqual(categories(r"\draw[direct] (0,0)--(.7,-.5);"), [])

    def test_numeric_detour_is_legal_by_default(self):
        self.assertEqual(categories(r"\draw[direct] (0,0)--(0,4)--(2,4)--(2,2);"), [])

    def test_named_endpoints_with_rails_are_not_short_or_long(self):
        text = node("a", 0, 0) + node("b", .5, 2) + "\n" + r"\draw[direct] (a.east)--(8,0)--(8,2)--(b.east);"
        self.assertFalse(set(categories(text)) & {"direction", "short-arrow", "long-arrow", "micro-slope"})

    def test_orthogonal_contract_detects_diagonal(self):
        text = r"\draw[->] (0,0)--(.7,-.5); % tikz-validator: orthogonal"
        self.assertIn("micro-slope", categories(text))

    def test_valid_orthogonal_rail(self):
        text = r"\draw[->] (0,0)--(0,4)--(2,4)--(2,2); % tikz-validator: orthogonal"
        self.assertEqual(categories(text), [])

    def test_monotone_contract_is_optional_and_explicit(self):
        text = r"\draw[->] (0,0)--(0,4)--(2,4)--(2,2); % tikz-validator: monotone-y"
        self.assertIn("direction", categories(text))

    def test_named_endpoint_contract_reports_coverage_not_false_target(self):
        text = r"\draw[->] (a.east)--(8,0)--(8,2)--(b.east); % tikz-validator: monotone-y"
        self.assertIn("coverage", categories(text))
        self.assertNotIn("direction", categories(text))

    def test_explicit_edge_gap_for_straight_facing_anchors(self):
        text = node("a", 0, 0) + node("b", 1.5, 0) + "\n" + r"\draw[->] (a.east)--(b.west); % tikz-validator: edge-gap"
        self.assertIn("short-arrow", categories(text))

    def test_edge_gap_does_not_measure_waypoint_route(self):
        text = node("a", 0, 0) + node("b", 1.5, 0) + "\n" + r"\draw[->] (a.east)--(8,0)--(8,2)--(b.east); % tikz-validator: edge-gap"
        self.assertIn("coverage", categories(text))
        self.assertNotIn("short-arrow", categories(text))

    def test_long_straight_edge_has_no_maximum_length_rule(self):
        text = node("a", 0, 0) + node("b", 10, 0) + "\n" + r"\draw[->] (a.east)--(b.west); % tikz-validator: edge-gap"
        self.assertNotIn("long-arrow", categories(text))

    def test_unexpanded_route_style_or_transform_reports_coverage(self):
        for opts in ["direct", "rotate=20", "x=2cm"]:
            text = r"\draw[" + opts + r"] (0,0)--(.7,-.5); % tikz-validator: orthogonal"
            self.assertIn("coverage", categories(text))
            self.assertNotIn("micro-slope", categories(text))


class CommandLine(unittest.TestCase):
    def test_multiline_node_warns_with_exit_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "figure.tex"
            path.write_text(node("a", 0, 0, body=r"A\\B"), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"node-metrics", result.stdout)
        self.assertNotIn(b"PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
