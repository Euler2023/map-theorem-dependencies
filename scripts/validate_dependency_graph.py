#!/usr/bin/env python3
"""Audit an evidence ledger and its explicitly selected visible subgraph.

Usage:
  python validate_dependency_graph.py nodes.json edges.csv [--tex figure.tex]
      [--conclusion NODE_ID]... [--gate NODE_ID]...

Nodes JSON is an array or {"nodes": [...]}. Standard node fields are id, role,
visible/included (boolean or yes/no), selected_conclusion and selected_gate.
Top-level selected_conclusions/selected_gates arrays and repeatable CLI options
also select targets. role=foundation or foundation=true marks an origin;
role=context excludes a node from the proof spine.

CSV fields: source_id,target_id,relation,evidence_location,evidence. Optional
visible/included boolean or visual_route selects visible edges; ledger-only is
hidden. `included=grouped` hides the individual node but cannot validate a group
expansion. With --tex, `% EDGE source -> target [relation]` comments declare the
visible arrows. This checks declarations, not arbitrary TikZ drawing commands.

stdout is JSON. Exit codes: 0 no reported problems; 1 warnings/coverage gaps;
2 malformed structure, cycles or ledger/TeX inconsistency. Path warnings identify
items for source review, never a reason to invent an unsupported connection.
No mathematical statements, evidence truth or asserted equivalences are proved.
Only the Python standard library is required.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

RELATIONS = {
    "direct", "technical-input", "implication", "complementary-case",
    "alternative", "context",
}
EDGE_TAG = re.compile(r"^\s*%\s*EDGE\s+(\S+)\s*->\s*(\S+)\s*\[([^\]]+)\]\s*$")
EDGE_PREFIX = re.compile(r"^\s*%\s*EDGE(?:\s|$)")


def _flag(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"true", "yes", "1"}:
            return True
        if token in {"false", "no", "0"}:
            return False
        if not token:
            return None
    if value is None:
        return None
    raise ValueError(f"Expected boolean or yes/no, got {value!r}")


def _cycles(adjacency):
    """Return at most twenty DFS cycle witnesses; no recursive stack limit."""
    colors, path, positions, found = {}, [], {}, []
    for root in sorted(adjacency):
        if colors.get(root, 0):
            continue
        colors[root] = 1
        positions[root] = len(path)
        path.append(root)
        stack = [(root, iter(sorted(adjacency[root])))]
        while stack:
            vertex, children = stack[-1]
            child = next(children, None)
            if child is None:
                stack.pop()
                colors[vertex] = 2
                positions.pop(vertex, None)
                path.pop()
            elif colors.get(child, 0) == 0:
                colors[child] = 1
                positions[child] = len(path)
                path.append(child)
                stack.append((child, iter(sorted(adjacency[child]))))
            elif colors[child] == 1 and len(found) < 20:
                found.append(path[positions[child]:] + [child])
    return found


def _reachable(starts, adjacency):
    seen, pending = set(starts), list(starts)
    while pending:
        for neighbor in adjacency[pending.pop()]:
            if neighbor not in seen:
                seen.add(neighbor)
                pending.append(neighbor)
    return seen


def audit(nodes_data, edge_rows, tex_text=None, conclusions=(), gates=()):
    """Return a JSON-serializable report; useful directly from behavior tests."""
    issues, coverage = [], {}

    def issue(level, code, message, graph=None, **details):
        item = {"level": level, "code": code, "message": message}
        if graph:
            item["graph"] = graph
        item.update(details)
        issues.append(item)

    metadata = nodes_data if isinstance(nodes_data, dict) else {}
    raw_nodes = metadata.get("nodes") if metadata else nodes_data
    if not isinstance(raw_nodes, list):
        issue("error", "invalid_nodes", "Nodes JSON must be an array or an object with a nodes array.")
        raw_nodes = []
    nodes, node_visibility, foundations = {}, {}, set()
    chosen_conclusions, chosen_gates = set(conclusions), set(gates)

    def boolean(obj, key, location):
        try:
            return _flag(obj.get(key))
        except ValueError as exc:
            issue("error", "invalid_boolean", str(exc), location=location, field=key)
            return None

    def visibility(obj, location, node=False):
        declared = []
        for key in ("visible", "included"):
            if node and str(obj.get(key, "")).lower() == "grouped":
                declared.append(False)
                issue("warning", "group_expansion_not_checked",
                      "Grouped members are hidden; a separate explicit group node and edges must be audited.",
                      location=location)
            elif key in obj:
                value = boolean(obj, key, location)
                if value is not None:
                    declared.append(value)
        if not node and str(obj.get("visual_route", "")).strip():
            declared.append(str(obj["visual_route"]).strip().lower() != "ledger-only")
        if len(set(declared)) > 1:
            issue("error", "conflicting_visibility", "Visibility declarations disagree.", location=location)
        return declared[0] if declared else None

    for index, node in enumerate(raw_nodes, 1):
        location = f"node[{index}]"
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or not node["id"].strip():
            issue("error", "missing_node_id", "Each node needs a nonempty string id.", location=location)
            continue
        identifier = node["id"].strip()
        if identifier in nodes:
            issue("error", "duplicate_node_id", "Node IDs must be unique.", nodes=[identifier])
            continue
        nodes[identifier] = node
        node_visibility[identifier] = visibility(node, identifier, node=True)
        if node.get("role") == "foundation" or boolean(node, "foundation", identifier) is True:
            foundations.add(identifier)
        for key, selected in (("selected_conclusion", chosen_conclusions), ("selected_gate", chosen_gates)):
            if boolean(node, key, identifier) is True:
                selected.add(identifier)

    for key, selected in (("selected_conclusions", chosen_conclusions), ("selected_gates", chosen_gates)):
        values = metadata.get(key, [])
        if not isinstance(values, list) or not all(isinstance(v, str) and v.strip() for v in values):
            issue("error", "invalid_selection", f"{key} must be an array of nonempty node IDs.")
        else:
            selected.update(v.strip() for v in values)
    selected = chosen_conclusions | chosen_gates
    missing_selected = selected - nodes.keys()
    if missing_selected:
        issue("error", "unknown_selected_target", "Selected targets must exist in the node ledger.", nodes=sorted(missing_selected))
    coverage["target_selection"] = "explicit" if selected else "not-provided"
    if not selected:
        issue("warning", "target_selection_missing",
              "No selected conclusion/gate was declared; reachability-to-purpose cannot be audited. Roles alone do not select targets.")

    edges, edge_visibility, seen_edges, seen_pairs = [], {}, set(), {}
    for index, raw_edge in enumerate(edge_rows, 2):
        if not isinstance(raw_edge, dict):
            issue("error", "invalid_edge", "Each CSV row must be an object.", row=index)
            continue
        edge = {key: str(value).strip() if value is not None else "" for key, value in raw_edge.items()}
        source, target, relation = (edge.get(key, "") for key in ("source_id", "target_id", "relation"))
        triple = (source, target, relation)
        if not source or not target:
            issue("error", "missing_edge_endpoint", "Every edge needs source_id and target_id.", row=index)
        unknown = {value for value in (source, target) if value and value not in nodes}
        if unknown:
            issue("error", "unknown_edge_endpoint", "Edge endpoints must exist in the node ledger.", row=index, nodes=sorted(unknown))
        if relation not in RELATIONS:
            issue("error", "invalid_relation", "Use exactly one recognized primary relation; an equivalence claim is not a cycle exemption.", row=index, relation=relation)
        for key in ("evidence_location", "evidence"):
            if not edge.get(key):
                issue("error", "missing_edge_evidence", f"Every edge needs nonempty {key}.", row=index, field=key)
        if triple in seen_edges:
            issue("error", "duplicate_edge", "An edge triple is duplicated.", row=index, edge=list(triple))
        seen_edges.add(triple)
        pair = (source, target)
        if pair in seen_pairs and seen_pairs[pair] != relation:
            issue("error", "conflicting_edge_relation", "The same directed pair has different primary relations.", row=index, edge=[source, target])
        seen_pairs[pair] = relation
        edge_visibility[triple] = visibility(raw_edge, f"CSV row {index}")
        edges.append(edge)

    tagged_edges = set()
    if tex_text is not None:
        for line_no, line in enumerate(tex_text.splitlines(), 1):
            match = EDGE_TAG.match(line)
            if not match:
                if EDGE_PREFIX.match(line):
                    issue("error", "malformed_tex_edge", "Expected % EDGE source -> target [relation].", line=line_no)
                continue
            triple = (match[1], match[2], match[3].strip())
            if triple in tagged_edges:
                issue("warning", "duplicate_tex_edge", "The same arrow is annotated more than once.", line=line_no, edge=list(triple))
            tagged_edges.add(triple)
            if triple not in seen_edges:
                issue("error", "tex_edge_not_in_ledger", "A declared visible arrow has no identical evidence-ledger edge.", line=line_no, edge=list(triple))
            elif edge_visibility[triple] is False:
                issue("error", "tex_hidden_edge", "TeX declares an edge marked hidden in the ledger.", line=line_no, edge=list(triple))
        for triple, visible in edge_visibility.items():
            if visible is True and triple not in tagged_edges:
                issue("error", "visible_edge_not_in_tex", "A ledger-visible edge is missing from TeX annotations.", edge=list(triple))
        if not tagged_edges:
            issue("warning", "tex_edge_annotations_missing", "No EDGE annotations found; arbitrary TikZ arrows were not inspected.")
        coverage["tex"] = "annotation-consistency-only"
    else:
        coverage["tex"] = "not-requested"

    unknown_nodes = sorted(identifier for identifier, flag in node_visibility.items() if flag is None)
    unknown_edges = [triple for triple, flag in edge_visibility.items() if flag is None]
    if unknown_nodes:
        issue("warning", "node_visibility_incomplete", "Node visibility is undeclared; isolated visible nodes cannot be inferred from edge annotations.", nodes=unknown_nodes)
    if unknown_edges and tex_text is None:
        issue("warning", "edge_visibility_incomplete", "Some edge visibility is undeclared; the complete ledger is not assumed to be the visible subgraph.", count=len(unknown_edges))
    coverage["node_visibility"] = "explicit" if not unknown_nodes else "partial-or-missing"
    coverage["edge_visibility"] = ("tex-annotations" if tex_text is not None else
                                    "explicit" if not unknown_edges else "partial-or-missing")

    context_nodes = {identifier for identifier, node in nodes.items() if node.get("role") == "context"}
    if selected & context_nodes:
        issue("error", "selected_context_node", "A selected conclusion/gate cannot also be context.", nodes=sorted(selected & context_nodes))
    for edge in edges:
        if edge.get("relation") != "context" and {edge.get("source_id"), edge.get("target_id")} & context_nodes:
            issue("warning", "context_node_proof_edge", "A non-context edge touches a context node; review the role assignment.", edge=[edge.get("source_id"), edge.get("target_id")])

    def check_graph(name, identifiers, triples):
        active = set(identifiers) - context_nodes
        adjacency = {identifier: set() for identifier in active}
        reverse = {identifier: set() for identifier in active}
        proof_edges = set()
        for source, target, relation in triples:
            if relation != "context" and source in active and target in active:
                adjacency[source].add(target)
                reverse[target].add(source)
                proof_edges.add((source, target, relation))
        cycle_witnesses = _cycles(adjacency)
        for cycle in cycle_witnesses:
            issue("error", "directed_cycle", "The proof graph is cyclic. Asserted equivalence requires source review and an explicitly redesigned acyclic representation; it is not auto-accepted.", graph=name, nodes=cycle)
        targets = selected & active
        origins = foundations & active
        result = {"node_count": len(active), "proof_edge_count": len(proof_edges),
                  "selected_targets": sorted(targets), "foundations": sorted(origins),
                  "cycles": cycle_witnesses}
        if not targets:
            result["reachability"] = "not-audited-no-selected-targets"
            if selected:
                issue("warning", "selected_targets_not_visible", "No selected conclusion/gate is in this subgraph; purpose reachability is unaudited.", graph=name)
            return result
        unserved = active - _reachable(targets, reverse)
        without_incoming = {target for target in targets if not reverse[target]}
        result.update({"reachability": "audited", "nodes_without_target_path": sorted(unserved),
                       "targets_without_incoming": sorted(without_incoming)})
        if unserved:
            issue("warning", "no_path_to_selected_target", "These nodes do not reach a selected conclusion/gate. Check scope, exclusions or missing evidence; do not invent connecting edges.", graph=name, nodes=sorted(unserved))
        if without_incoming:
            issue("warning", "selected_target_no_incoming", "A selected conclusion/gate has no incoming proof path in this graph.", graph=name, nodes=sorted(without_incoming))
        if not origins:
            result["foundation_reachability"] = "not-audited-no-foundations"
            issue("warning", "foundation_markers_missing", "No role=foundation or foundation=true nodes exist in this graph; origin reachability is unaudited.", graph=name)
        else:
            unanchored = targets - _reachable(origins, adjacency)
            result["targets_without_foundation_path"] = sorted(unanchored)
            if unanchored:
                issue("warning", "target_not_reached_from_foundation", "A selected conclusion/gate is not reached from an explicitly marked foundation.", graph=name, nodes=sorted(unanchored))
        return result

    full = check_graph("complete", set(nodes), seen_edges)
    visible_triples = (tagged_edges & seen_edges if tex_text is not None else
                       {triple for triple, flag in edge_visibility.items() if flag is True})
    visible_nodes = {identifier for identifier, flag in node_visibility.items() if flag is True}
    for source, target, _relation in visible_triples:
        for identifier in (source, target):
            if identifier not in nodes:
                continue
            if node_visibility[identifier] is False:
                issue("error", "visible_edge_hidden_endpoint", "A visible arrow has an explicitly hidden endpoint.", nodes=[identifier], edge=[source, target])
            else:
                visible_nodes.add(identifier)
    visible_available = bool(visible_nodes or visible_triples or all(flag is not None for flag in node_visibility.values()))
    visible = check_graph("visible", visible_nodes, visible_triples) if visible_available else {"reachability": "not-audited-no-visibility-declarations"}
    levels = {entry["level"] for entry in issues}
    exit_code = 2 if "error" in levels else 1 if "warning" in levels else 0
    return {"status": ["pass", "warning", "error"][exit_code], "exit_code": exit_code,
            "coverage": coverage, "counts": {"nodes": len(nodes), "edges": len(edges)},
            "graphs": {"complete": full, "visible": visible}, "issues": issues,
            "limitations": ["Graph structure and declared evidence presence only; evidence truth and mathematical validity require source review.",
                            "TeX checks use EDGE comments only and do not discover unannotated drawing commands.",
                            "Reachability is necessary bookkeeping, not proof completeness: AND gates, case coverage and true alternatives require manual audit."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("nodes", type=Path)
    parser.add_argument("edges", type=Path)
    parser.add_argument("--tex", type=Path)
    parser.add_argument("--conclusion", action="append", default=[], metavar="NODE_ID")
    parser.add_argument("--gate", action="append", default=[], metavar="NODE_ID")
    args = parser.parse_args(argv)
    try:
        nodes = json.loads(args.nodes.read_text(encoding="utf-8-sig"))
        with args.edges.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"source_id", "target_id", "relation", "evidence_location", "evidence"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ValueError("Edges CSV requires columns: " + ", ".join(sorted(required)))
            rows = list(reader)
            if any(None in row for row in rows):
                raise ValueError("CSV rows contain extra fields; quote commas inside evidence text.")
        tex = args.tex.read_text(encoding="utf-8-sig") if args.tex else None
        report = audit(nodes, rows, tex, args.conclusion, args.gate)
    except (OSError, ValueError, csv.Error) as exc:
        report = {"status": "error", "exit_code": 2,
                  "issues": [{"level": "error", "code": "input_error", "message": str(exc)}]}
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
