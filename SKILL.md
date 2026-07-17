---
name: map-theorem-dependencies
description: Extract, verify, and visualize theorem-level logical dependencies from mathematical papers, theses, books, and LaTeX/Markdown/PDF projects. Use when Codex must build a dependency graph or proof roadmap for theorems, propositions, lemmas, and corollaries; distinguish direct proof inputs from implications, alternative proof routes, background results, and mere mentions; produce a reader-reviewable Mermaid proof skeleton; or deliver an evidence-backed publication-ready TikZ/PDF/PNG theorem dependency map.
---

# Map Theorem Dependencies

Recover the mathematical proof architecture before drawing it. Treat every edge as a claim requiring local textual evidence, then use `$thesis-figure-skill` for TikZ design, compilation, and visual audit.

## Required outputs

Produce these artifacts unless the user narrows the scope:

1. `dependency-ledger.md` or `.csv`: every included result, exact identifier, source location, short statement, and role.
2. `dependency-edges.csv`: source, target, relation, evidence location, evidence paraphrase, and confidence.
3. `dependency-draft.md` or an in-conversation Mermaid diagram: a curated, readable main-proof skeleton for semantic and layout review.
4. A standalone TikZ `.tex`, compiled vector `.pdf`, and rendered `.png` preview when the user requests a finished figure.
5. `dependency-audit.md`: exclusions, grouped nodes, uncertain edges, numbering drift, and validation results.

Do not draw an edge that cannot be traced to the ledger. Do not present a thematic association as a proof dependency.

## Workflow

### 1. Establish the source hierarchy

Inspect the project locally before searching elsewhere.

1. Locate the main assembly file, chapter order, included files, bibliography, manifest, and any existing roadmap or Leitfaden figure.
2. Treat a manifest as a structural hint, not as an authoritative theorem inventory; verify it against the source files.
3. Prefer proofread LaTeX or Markdown. For PDF-only sources, extract text with `pdftotext`, then render pages when symbols or numbering are ambiguous.
4. Record translated/original numbering aliases when both exist.

Use `rg --files` and `rg` first. Read [references/dependency-evidence.md](references/dependency-evidence.md) before extracting edges.

### 2. Inventory theorem-like objects

Find theorem, proposition, lemma, corollary, definition, and named-result environments. Capture:

- stable ID and displayed number;
- type and concise title or statement;
- source file and line or PDF page;
- proof span;
- role: foundation, main bound, application construction, contradiction input, final conclusion, consequence, comparison, or context.

Use document assembly order to resolve numbering. Detect duplicate labels, aliases such as “Theorem C = Theorem 14.0.1,” and numbering drift between source, translation, and compiled output.

### 3. Extract evidence-backed edges

Read proofs and explicit cross-references, not only result statements. Classify each edge using exactly one primary relation:

- `direct`: the target proof explicitly invokes or logically requires the source;
- `technical-input`: the source supplies an estimate, construction, dictionary, contour, denominator, or other enabling tool;
- `implication`: the target is a stated corollary, specialization, limit, or generalization relation;
- `alternative`: the source is one of several substitutable routes to the same gate or conclusion;
- `context`: comparison or background only; normally keep it outside the main directed spine.

Require file/line or PDF-page evidence for `direct`, `technical-input`, and `alternative`. Mark inference explicitly and lower confidence when a proof uses an unnamed result whose identity must be reconstructed.

Never infer an edge merely because two results occur in adjacent chapters, share terminology, cite the same paper, appear together in an introduction, or coexist in a high-level roadmap.

### 4. Build the proof spine before styling

Identify final conclusions first and work backward.

1. Recover each contradiction or closure gate.
2. Separate construction branches from analytic or arithmetic bound branches.
3. Preserve genuinely alternative proof routes instead of flattening them into one chain.
4. Group low-level lemmas only when they serve the same function and no later edge needs an individual lemma.
5. Put results that do not participate in selected main proofs into a separate context band.
6. If the graph is too dense, deliver a complete ledger plus a curated main-proof graph; never silently discard nodes.

Run semantic checks before drawing:

- every main conclusion has an incoming proof path;
- every non-context node reaches a selected conclusion or labeled intermediate result;
- alternative routes converge at a named gate;
- no directed cycle exists unless the document truly contains equivalence;
- each edge direction reads “source is used to establish target.”

### 5. Draft the reviewed proof skeleton in Mermaid

Create the Mermaid graph before publication typesetting. Treat it as the semantic and spatial prototype, not as disposable scaffolding.

1. Show the curated main proof first; keep the complete inventory in the ledger.
2. Use subgraphs for genuine proof modules, not merely chapter boundaries.
3. Give every visible module a reader-facing full name. Never expose internal IDs such as `F`, `APP`, or `ALG`. Expand a standard acronym at first appearance, for example `Gross–Kohnen–Zagier (GKZ)`.
4. Keep node labels short but mathematical: exact result type and number plus a faithful content phrase.
5. Express shared foundations by branching from the common result. Do not draw a module-to-module arrow unless a theorem in the first module is actually used in the second.
6. Preserve parallel branches and whitespace. Avoid forcing a naturally branching graph into uniform columns.
7. In an interactive task, present the Mermaid draft for reader feedback before committing to TikZ when the user has not already approved a layout.

The reviewed Mermaid geometry is a layout contract for the finished figure: preserve its relative placement, branch direction, grouping, and visual breathing room unless a concrete rendering defect requires a change.

### 6. Write the figure design brief

Materialize the design brief before editing TikZ. State:

- domain and terminology policy;
- selected result scope;
- logical flow direction;
- zones and semantic roles;
- hero structure remembered after five seconds;
- edge-to-style mapping;
- rail and junction strategy;
- grouping and context-band policy;
- page size and smallest allowed font;
- likely congestion points.

Choose the canvas after seeing the Mermaid topology. Prefer a wide custom vector canvas for a wide graph; do not compress it into A4 merely because the deliverable is a PDF. For a genuinely four-stage linear architecture, start from [assets/theorem-dependency-four-zone.tex](assets/theorem-dependency-four-zone.tex). Use it only when the topology matches and no reviewed draft establishes a better layout.

### 7. Draw with the companion figure skill

Announce and use `$thesis-figure-skill` for the visual production phase. Follow its current rules instead of copying them here.

Preserve this semantic encoding unless the user requests another:

- solid dark arrow: direct proof dependency;
- thin gray arrow: technical input;
- emphasized dashed or double-dashed colored arrow: alternative route;
- dotted gray arrow: implication, specialization, or generalization;
- separate low-saturation band: context not used in the main proof.

Prefer functional color zones over coloring by theorem type. A theorem, proposition, lemma, and corollary in the same module may share a color; their formal kind must remain explicit in the text. Use a neutral gray-blue treatment for technical inputs and the strongest border/fill treatment for branch conclusions. Include a compact box-color legend so readers do not infer that colors encode result type.

Apply emphasis consistently:

- bold the identifier line for branch conclusions and results identified with an introduction-level theorem;
- keep explanatory text at regular weight;
- use `=` only for numbering aliases or literally identical results;
- use `\Rightarrow` when one result implies another rather than being the same numbered result;
- do not bold an ordinary intermediate result merely because it has two nearby references.

Preserve the approved Mermaid layout. Increase the canvas or reroute rails before shrinking fonts or collapsing whitespace.

Keep production language out of the finished figure. Do not print notes such as “preserves the Mermaid layout,” “semantic audit,” “AI generated,” or other workflow commentary. Put audit details in `dependency-audit.md`. If provenance is useful, use a neutral date label such as `制作时间：YYYY-MM-DD` or a conventional figure caption.

For dense graphs, route long cross-zone edges on dedicated rails. Merge multiple prerequisite branches at visible junctions before entering a conclusion. Do not let an edge pass through an unrelated node or label.

### 8. Validate semantics and rendering

Perform both audits; one cannot replace the other.

#### Semantic audit

- Re-open source evidence for every main-spine edge.
- Check theorem numbers, aliases, arrow directions, and grouped labels.
- Distinguish “used in proof” from “related to” in the legend and audit.
- List all uncertain or inferred edges rather than silently upgrading them.
- Verify that a high-level roadmap guided scope only and did not create unsupported theorem-level edges.

#### Visual audit

Use the complete compile, render, and review loop required by `$thesis-figure-skill`. In addition, inspect:

- long labels touching zone or page boundaries;
- routes crossing intermediate theorem boxes;
- alternative routes forming an unreadable knot;
- visual arrow direction opposite to logical dependency;
- final theorems receiving parallel lines without a clear junction;
- contextual results appearing to feed the main proof;
- theorem numbers unreadable after whole-page scaling.
- unexplained abbreviations or internal module IDs in visible text;
- box colors that lack a legend or appear to encode theorem type accidentally;
- inconsistent bolding of analogous conclusion or alias nodes;
- process commentary that belongs in the audit rather than the published figure.

Fix routing and spatial allocation before reducing font size. Recompile and inspect the PNG after each routing change.

## Quality gates

Do not claim completion until all are true:

- Every included edge has evidence and a relation class.
- Every theorem number is checked against its rendered source.
- Main proof paths and alternative routes are visually distinguishable.
- The Mermaid skeleton was reviewed or explicitly used as the layout reference.
- Excluded and grouped results are documented.
- Visible abbreviations are expanded, box-color semantics are explained, and emphasis rules are consistent.
- TikZ compiles without missing characters or overflow warnings.
- PDF is nonzero, opens normally, and has the expected page count.
- PNG inspection confirms readable type, unobstructed arrows, and clear hierarchy.

## Scope discipline

When evidence is incomplete, deliver a partial graph with explicit gaps. Never manufacture a dependency to make the diagram connected. When the user requests only analysis, stop after the ledger and graph specification; do not create files unless asked.
