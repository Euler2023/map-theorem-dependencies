#!/usr/bin/env python3
"""Behavior tests for ledger structure, visible pruning and audit coverage."""

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from validate_dependency_graph import audit


def node(identifier, role="construction", **fields):
    return dict(id=identifier, role=role, visible=True, **fields)


def edge(source, target, **fields):
    result = dict(source_id=source, target_id=target, relation="direct",
                  evidence_location="p.2, proof", evidence="Target explicitly invokes source.", visible="true")
    result.update(fields)
    return result


def codes(report, graph=None):
    return {issue["code"] for issue in report["issues"] if graph is None or issue.get("graph") == graph}


class DependencyGraphTests(unittest.TestCase):
    def setUp(self):
        self.nodes = [node("input", "foundation"), node("middle"),
                      node("result", "conclusion", selected_conclusion=True)]
        self.edges = [edge("input", "middle"), edge("middle", "result")]

    def test_legal_full_and_visible_graph(self):
        report = audit({"nodes": self.nodes}, self.edges)
        self.assertEqual(report["exit_code"], 0, report)
        self.assertEqual(report["graphs"]["visible"]["proof_edge_count"], 2)
        self.assertEqual(report["graphs"]["complete"]["nodes_without_target_path"], [])

    def test_orphan_is_review_warning_not_invented_edge(self):
        report = audit(self.nodes + [node("orphan")], self.edges)
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["graphs"]["complete"]["nodes_without_target_path"], ["orphan"])
        self.assertEqual(report["counts"]["edges"], 2)

    def test_pruned_critical_edge_breaks_visible_only(self):
        self.edges[1]["visible"] = "false"
        report = audit(self.nodes, self.edges)
        self.assertEqual(report["exit_code"], 1)
        self.assertNotIn("no_path_to_selected_target", codes(report, "complete"))
        self.assertIn("no_path_to_selected_target", codes(report, "visible"))
        self.assertIn("selected_target_no_incoming", codes(report, "visible"))
        self.assertEqual(report["graphs"]["visible"]["proof_edge_count"], 1)

    def test_duplicate_node_id(self):
        report = audit(self.nodes + [node("input")], self.edges)
        self.assertEqual(report["exit_code"], 2)
        self.assertIn("duplicate_node_id", codes(report))

    def test_unknown_endpoint(self):
        report = audit(self.nodes, self.edges + [edge("absent", "result")])
        self.assertEqual(report["exit_code"], 2)
        self.assertIn("unknown_edge_endpoint", codes(report))

    def test_cycles_not_excused_by_equivalence_claim(self):
        self.nodes[1]["equivalence"] = True
        report = audit(self.nodes, self.edges + [edge("result", "middle", equivalence="true")])
        self.assertEqual(report["exit_code"], 2)
        self.assertIn("directed_cycle", codes(report, "complete"))
        self.assertIn("directed_cycle", codes(report, "visible"))

    def test_context_relation_does_not_create_proof_cycle(self):
        report = audit(self.nodes, self.edges + [edge("result", "input", relation="context")])
        self.assertEqual(report["exit_code"], 0, report)

    def test_edge_without_source_evidence_is_error(self):
        self.edges[0]["evidence"] = ""
        self.edges[1]["evidence_location"] = ""
        report = audit(self.nodes, self.edges)
        self.assertEqual(report["exit_code"], 2)
        missing = [i for i in report["issues"] if i["code"] == "missing_edge_evidence"]
        self.assertEqual({i["field"] for i in missing}, {"evidence", "evidence_location"})

    def test_tex_unledgered_arrow_and_missing_declared_arrow(self):
        report = audit(self.nodes, self.edges, "% EDGE input -> result [direct]\n")
        self.assertEqual(report["exit_code"], 2)
        self.assertIn("tex_edge_not_in_ledger", codes(report))
        self.assertIn("visible_edge_not_in_tex", codes(report))

    def test_tex_matching_annotations(self):
        tex = "% EDGE input -> middle [direct]\n% EDGE middle -> result [direct]\n"
        report = audit(self.nodes, self.edges, tex)
        self.assertEqual(report["exit_code"], 0, report)

    def test_tex_hidden_endpoint(self):
        self.nodes[1]["visible"] = False
        report = audit(self.nodes, self.edges)
        self.assertEqual(report["exit_code"], 2)
        self.assertIn("visible_edge_hidden_endpoint", codes(report))

    def test_missing_selection_and_visibility_are_coverage_warning(self):
        unmarked_nodes = [{"id": "a", "role": "foundation"}, {"id": "b", "role": "conclusion"}]
        unmarked_edge = edge("a", "b")
        del unmarked_edge["visible"]
        report = audit(unmarked_nodes, [unmarked_edge])
        self.assertEqual(report["exit_code"], 1)
        self.assertTrue({"target_selection_missing", "node_visibility_incomplete", "edge_visibility_incomplete"} <= codes(report))
        self.assertEqual(report["graphs"]["complete"]["reachability"], "not-audited-no-selected-targets")

    def test_selected_gate_and_top_level_selection(self):
        del self.nodes[2]["selected_conclusion"]
        report = audit({"nodes": self.nodes, "selected_gates": ["result"]}, self.edges)
        self.assertEqual(report["exit_code"], 0, report)

    def test_visual_route_ledger_only_prunes_edge(self):
        for item in self.edges:
            del item["visible"]
            item["visual_route"] = "main"
        self.edges[1]["visual_route"] = "ledger-only"
        report = audit(self.nodes, self.edges)
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["graphs"]["complete"]["proof_edge_count"], 2)
        self.assertEqual(report["graphs"]["visible"]["proof_edge_count"], 1)

    def test_unknown_relation_and_duplicate_edge(self):
        report = audit(self.nodes, self.edges + [dict(self.edges[0]), edge("result", "input", relation="equivalence")])
        self.assertEqual(report["exit_code"], 2)
        self.assertTrue({"invalid_relation", "duplicate_edge", "directed_cycle"} <= codes(report))

    def test_cli_json_output_and_exit_codes(self):
        script = Path(__file__).with_name("validate_dependency_graph.py")
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            nodes_path, edges_path = base / "nodes.json", base / "edges.csv"
            nodes_path.write_text(json.dumps(self.nodes), encoding="utf-8")
            with edges_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(self.edges[0]))
                writer.writeheader()
                writer.writerows(self.edges)
            result = subprocess.run([sys.executable, str(script), str(nodes_path), str(edges_path)], capture_output=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "pass")
            edges_path.write_text("source_id,target_id\na,b\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(script), str(nodes_path), str(edges_path)], capture_output=True, encoding="utf-8")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["issues"][0]["code"], "input_error")


if __name__ == "__main__":
    unittest.main()
