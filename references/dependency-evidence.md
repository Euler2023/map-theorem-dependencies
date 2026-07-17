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

## 3. Edge schema

| Field | Meaning |
|---|---|
| `source_id` | Result used as an input |
| `target_id` | Result established using the source |
| `relation` | direct, technical-input, implication, alternative, context |
| `evidence_location` | Exact file/line or PDF page |
| `evidence` | Short paraphrase |
| `confidence` | high, medium, low |
| `inference` | `false` or concise explanation |
| `visual_route` | main, upper-rail, lower-rail, local, context-band |

Arrow direction is always `source_id -> target_id`: the source contributes to proving the target.

## 4. Evidence hierarchy

1. **High**: the target proof explicitly cites the source by number or name.
2. **High**: a corollary or specialization is declared immediately and unambiguously.
3. **Medium**: the proof invokes a uniquely identifiable construction or estimate without its number.
4. **Medium**: an introduction or proof overview specifies the dependency and the detailed proof agrees.
5. **Low**: reconstruction from matching hypotheses and conclusions with no explicit citation. Include only when necessary and label inferred.
6. **Not an edge**: thematic similarity, neighboring placement, shared terminology, shared citation, or an overview that only lists both results.

Verify or expose every low-confidence main-spine edge as a gap.

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

## 6. Pruning and grouping

Use a complete ledger and a curated figure. Group results only when they share a functional role, enter the same route or target, remain interpretable as a group, and retain every displayed identifier.

Do not group results to hide routing problems. Do not place a theorem in the context band if it contributes to a selected main conclusion.

## 7. Semantic audit

Check programmatically where practical:

- all edge endpoints exist in the inventory;
- no duplicate machine IDs;
- every included non-context node has a path to a selected conclusion;
- every conclusion is reachable from a foundational input;
- no unexpected cycle;
- every `alternative` edge targets a shared gate or equivalent conclusion;
- all labels use identifiers found in the source.

Then manually verify the main spine and every low-confidence edge.

## 8. Lessons from a successful project

1. Use the manifest to discover structure, but verify the actual assembly and chapter sources.
2. Extract numbered environments first; then read proof references. Raw keyword scans mix dependencies with exposition.
3. Use an existing Leitfaden for macro architecture, not as evidence for theorem-level arrows.
4. Represent alternative proof methods as separate routes converging at a contradiction or dimension gate.
5. Move application-specific analytic inputs close to their application nodes instead of drawing distant lines.
6. Keep supplementary theorems outside the main spine in a labeled context band.
7. Route cross-zone arrows on dedicated rails and merge prerequisites at junction dots before conclusions.
8. During visual review, prioritize line-through-node defects, crowded routes, boundary labels, and theorem-number readability.
