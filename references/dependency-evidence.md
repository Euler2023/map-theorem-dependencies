# Dependency evidence and ledger specification

## Contents

1. Source discovery
2. Result inventory schema
3. Edge schema
4. Evidence hierarchy
5. Extraction patterns
6. Pruning and grouping
7. Semantic audit
8. Lessons from a successful project

## 1. Source discovery

Use this priority order:

1. Main LaTeX assembly and included `.tex` files.
2. Proofread Markdown organized by chapter.
3. Compiled PDF for displayed numbering and visual ambiguity checks.
4. Extracted PDF text for search and navigation.
5. Manifest, table of contents, source ledger, or existing roadmap as secondary hints.

Do not assume a manifest covers the complete document. A conversion manifest may describe only one section or processing stage.

## 2. Result inventory schema

| Field | Meaning |
|---|---|
| `id` | Stable machine ID such as `thm-6.0.2` |
| `display_id` | Printed identifier such as `Theorem 6.0.2` or `Theorem A` |
| `aliases` | Equivalent identifiers in another edition or location |
| `kind` | theorem, proposition, lemma, corollary, definition, named result |
| `short_label` | Node-sized mathematical summary |
| `statement_summary` | Faithful one- or two-sentence summary |
| `source` | File and line, or PDF page |
| `proof_source` | Proof span or page range |
| `role` | foundation, route, construction, gate, conclusion, consequence, context |
| `included` | yes, no, or grouped |
| `group_id` | Functional group when several lemmas share one node |
| `notes` | Numbering drift, ambiguity, translation issues |

Unnumbered constructions, equation blocks, and consequences are valid inventory objects; use `kind: unnumbered` rather than assigning a new formal number. Give synthetic gates a local ID and an honest formula/section label. Keep the printed identifier separate from the stable machine ID.

For automated validation, prefer JSON with a top-level `nodes` list. `included: true/false` (or `visible`) records displayed membership; `grouped` members remain outside the visible graph and carry `group_id`. Select terminal conclusions via `selected_conclusions` in the top-level object, node `selected_conclusion: true`, or the validator's `--conclusion` arguments. An intermediate selected gate can be marked separately. `role: conclusion` alone need not mean the audit's terminal target.

## 3. Edge schema

| Field | Meaning |
|---|---|
| `source_id` | Result used as an input |
| `target_id` | Result established using the source |
| `relation` | direct, technical-input, implication, complementary-case, alternative, context |
| `evidence_location` | Exact file/line or PDF page |
| `evidence` | Short paraphrase |
| `confidence` | high, medium, low |
| `inference` | `false` or concise explanation |
| `visual_route` | main, upper-rail, lower-rail, local, context-band |

Use `visible: true/false` for machine-readable edge visibility, or the supported compatibility convention `visual_route: ledger-only` for hidden edges. Do not rely on an omitted visibility field to mean a complete visual audit. Geometry-specific route text may be stored here, but visibility and source evidence must remain independently reviewable.

Arrow direction is always `source_id -> target_id`: the source contributes to proving the target.

## 4. Evidence hierarchy

1. **High**: the target proof explicitly cites the source by number or name.
2. **High**: a corollary or specialization is declared immediately and unambiguously.
3. **Medium**: the proof invokes a uniquely identifiable construction or estimate without its number.
4. **Medium**: an introduction or proof overview specifies the dependency and the detailed proof agrees.
5. **Low**: reconstruction from matching hypotheses and conclusions with no explicit citation. Include only when necessary and label inferred.
6. **Not an edge**: thematic similarity, neighboring placement, shared terminology, shared citation, or an overview that only lists both results.

Verify or expose every low-confidence main-spine edge as a gap.

Confidence concerns the **dependency evidence**, not a certification of the theorem. Separate any certificate reproduction from full proof verification. If supplementary code is absent, inspect whether the paper itself supplies exact data and arithmetic instructions before declaring a gap. If only a finite certificate was checked, state that scope and the unverified upstream arguments.

## 5. Extraction patterns

Start with searches tailored to source format. Typical LaTeX searches:

```powershell
rg -n "\\\\begin\{(theorem|proposition|lemma|corollary|definition)\}|\\\\label\{(thm|prop|lem|cor)" path/to/tex
rg -n "(Theorem|Proposition|Lemma|Corollary|定理|命题|引理|推论)[ ~\\\\ref\{0-9A-Z]" path/to/tex
rg -n "(by|using|from|follows from|由|利用|根据|结合).*?(Theorem|Proposition|Lemma|定理|命题|引理)" path/to/tex
```

Inspect proof environments, introductions, summary roadmaps, and appendix inputs. Searches generate candidates; only reading the proof establishes an edge.

For PDF-only sources:

```powershell
pdftotext -layout source.pdf extracted.txt
rg -n "Theorem|Proposition|Lemma|Corollary|Proof" extracted.txt
```

Render ambiguous pages when formulas or theorem numbers are unreliable in extracted text.

Retain `\f` page separators, or split into numbered per-page files with explicit physical-page mapping. Record the source file and whether page/line numbering is printed, physical, or extracted. A keyword inventory can include bibliographic theorem numbers and prose references; verify each candidate's formal statement before counting it.

## 6. Pruning and grouping

Use a complete ledger and a curated figure. Group results only when they share a functional role, enter the same route or target, remain interpretable as a group, and retain every displayed identifier.

Do not group results to hide routing problems. Do not place a theorem in the context band if it contributes to a selected main conclusion.

When an identity feeds another branch but its subsequent estimate does not, split those objects. For example, a residue identity used in both denominator estimates and a nonvanishing argument must not be replaced by an edge saying that the denominator estimate proves nonvanishing. A composite group is allowed only when its members and used subparts remain explicit and no false shortcut is introduced.

Case labels must include the actual parameter domain. Two bounds may be globally valid yet be used on complementary domains; substitutability is a property of the proof route, not simply of their similar conclusions. A contradiction gate may jointly require rationality, a nonzero subsequence, and upper/lower estimates using the same normalization.

## 7. Semantic audit

Check programmatically where practical:

- all edge endpoints exist in the inventory;
- no duplicate machine IDs;
- every included non-context node has a path to a selected conclusion;
- every conclusion is reachable from a foundational input;
- no unexpected cycle;
- every `complementary-case` edge is one required parameter-range branch of the target;
- every `alternative` edge targets a shared gate or equivalent conclusion and is genuinely substitutable;
- all labels use identifiers found in the source.

Then manually verify the main spine and every low-confidence edge.

Run the bundled structural checker where the inventory is machine-readable:

```powershell
python "$SKILL_ROOT/scripts/validate_dependency_graph.py" dependency-nodes.json dependency-edges.csv --tex figure.tex --conclusion thm-main
```

The node argument can also be an object containing `nodes` such as an authoring snapshot, or a bare list. Use `--gate` for selected intermediate closure gates when needed. Annotate each displayed TikZ edge next to its `\draw` command:

```tex
% EDGE lemma-a -> thm-main [direct]
\draw[direct] (lemma-a.south)--(thm-main.north);
```

The checker compares those declarations to visible ledger edges, checks endpoints/duplicates/cycles and full versus visible reachability, and reports missing coverage. Comments are a traceability contract, **not a parser or proof of the rendered paths**: inspect the adjacent draw command and the PNG as well. Do not add artificial edges merely to silence disconnected-node warnings. Accepted equivalences should be collapsed to a documented group or reviewed explicitly, not globally exempted from cycle checks.

## 8. Lessons from a successful project

1. Use the manifest to discover structure, but verify the actual assembly and chapter sources.
2. Extract numbered environments first; then read proof references. Raw keyword scans mix dependencies with exposition.
3. Use an existing Leitfaden for macro architecture, not as evidence for theorem-level arrows.
4. Represent alternative proof methods as separate routes converging at a contradiction or dimension gate.
5. Move application-specific analytic inputs close to their application nodes instead of drawing distant lines.
6. Keep supplementary theorems outside the main spine in a labeled context band.
7. Route cross-zone arrows on dedicated rails and merge prerequisites at junction dots before conclusions.
8. During visual review, prioritize line-through-node defects, crowded routes, boundary labels, and theorem-number readability.
