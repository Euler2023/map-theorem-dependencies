---
name: map-theorem-dependencies
description: "Extract and audit source-evidenced logical dependencies between mathematical results, and draw proof-roadmap graphs when requested. Owns theorem-dependency Mermaid/TikZ/PDF production; ordinary geometry and system flowcharts use their figure skills."
---

# Map Theorem Dependencies

Recover the proof architecture before drawing it. Treat every edge and every displayed conclusion as a claim requiring local source evidence. This skill is self-contained; do not require or invoke another figure skill for theorem-map production.

Keep three questions separate: what the source claims, what it uses to prove the claim, and what this task actually verifies. A correct dependency map does not certify the mathematics. Do not turn extraction into a full proof audit or certificate recomputation unless requested or needed to resolve a specific edge.

## Outputs

For a substantial document audit, use the artifacts below; for a small graph, combine evidence and exclusions into one compact record or the answer. Create a finished figure only when requested:

1. `dependency-ledger.md` or `.csv`: exact result identifier, source location, concise statement, proof span, and role.
2. `dependency-edges.csv`: source, target, relation, evidence location, evidence paraphrase, and confidence.
3. `dependency-draft.md` or an in-conversation Mermaid diagram: a curated proof skeleton for review.
4. Standalone TikZ `.tex`, vector `.pdf`, and rendered `.png` when a finished figure is requested.
5. `dependency-audit.md`: exclusions, grouping decisions, uncertainty, numbering drift, and validation results.
6. `figure-qa.md` for a finished figure: page geometry, typography, semantic corrections, compiler checks, checker triage, and visual-review result.

For a substantial graph, keep a machine-readable node inventory (for example `dependency-nodes.json`) alongside the CSV. Mark which nodes and edges are visible and which conclusions are selected; the bundled semantic validator uses these distinctions. Small maps need not acquire extra files solely to satisfy a template.

Never draw an edge that is absent from the edge ledger. Never present thematic proximity as proof dependence.

## 1. Establish the source hierarchy

Inspect local material before searching elsewhere.

1. Locate the main assembly file, chapter order, included files, bibliography, manifests, and existing roadmaps.
2. Treat manifests and introduction roadmaps as scope hints, not authoritative edge inventories.
3. Prefer proofread LaTeX or Markdown. For PDF-only sources, run `pdftotext -layout`, then render ambiguous pages.
4. Record original/translated numbering aliases.
5. For a long PDF, optionally create a PIL contact sheet from low-resolution page renders for rapid structural orientation; use extracted text, not the contact sheet, as proof evidence.
6. When embedded raster figures may help identify structure or inspect source artwork, use Poppler's `pdfimages` workflow:

   ```bash
   command -v pdfimages
   pdfimages -list source.pdf
   mkdir -p extracted-images
   pdfimages -all source.pdf extracted-images/image
   # For a long source, restrict extraction with: -f FIRST_PAGE -l LAST_PAGE
   ```

   `pdfimages` is a Poppler utility (commonly in `poppler-utils`); it may already be bundled by a TeX or system distribution. It extracts embedded raster images at their stored resolution; it does not render complete pages or reliably recover vector line art, text, or TikZ. Use `pdftoppm` for whole-page PNG renders. Treat extracted images as orientation or visual-verification aids, never as sole evidence for theorem statements or dependency edges.

Check whether PDF page order matches printed page numbers. Keep page boundaries in extracted text. Keyword hits are candidates: a citation to another paper's “Theorem 1.1” is not an additional result in this source. Do not invent formal numbers for equation blocks or unnumbered consequences.

Use `rg --files` and `rg` first. Read [references/dependency-evidence.md](references/dependency-evidence.md) before extracting edges.

## 2. Inventory theorem-like objects

Capture theorem, proposition, lemma, corollary, definition, and named-result environments:

- stable ID and displayed number;
- exact source location;
- short faithful statement;
- proof span;
- role: foundation, estimate, construction, gate, conclusion, consequence, comparison, or context.

Resolve numbering from document assembly order. Detect duplicate labels, aliases, and drift between source, translation, and compiled output.

## 3. Extract evidence-backed edges

Read proofs and explicit cross-references, not only statements. Assign exactly one primary relation:

- `direct`: the target proof explicitly invokes or logically requires the source;
- `technical-input`: the source supplies an estimate, construction, dictionary, denominator, or enabling device;
- `implication`: stated corollary, specialization, limit, or generalization;
- `complementary-case`: sources cover disjoint parameter ranges that must be combined;
- `alternative`: genuinely substitutable proof routes;
- `context`: comparison or background only; normally outside the main directed spine.

Require page/line evidence for `direct`, `technical-input`, `complementary-case`, and `alternative`. For genuinely inferred dependencies, record the reconstruction and lower confidence.

An explicitly proved equation block may be an unnamed, high-confidence input: absence of a theorem number is not absence of evidence. Record its equations and proof span. Lower confidence for an inferred dependency, rather than automatically downgrading every unnamed step.

Do not infer an edge because two results are adjacent, share terminology, cite the same paper, or appear together in an introduction.

## 4. Build and audit the proof spine

Work backward from final conclusions.

1. Recover closure, contradiction, and case-split gates.
2. Separate dynamical, analytic, arithmetic, and construction branches.
3. Preserve complementary parameter ranges and true alternatives as different relations.
4. Group low-level lemmas only when they serve the same function and no later edge needs an individual member.
5. Put unused background results in a context band.
6. If the complete graph is too dense, keep the complete ledger and draw a curated main-proof graph; document every exclusion.

Split a module when a later proof uses one of its identities but not its final estimate. Name reconstruction/contradiction gates by their mathematical function, and keep all jointly required inputs. For an application, retain additional external value-identification or classification results instead of drawing an unsupported arrow from the main theorem alone.

Before drawing, verify:

- every selected conclusion has an incoming path;
- every non-context node reaches a selected conclusion or named gate;
- no unsupported shortcut edge replaces a multi-step argument;
- no directed cycle exists unless the source states an equivalence;
- each arrow reads “source is used to establish target.”

Check the complete graph **and the visible graph**. A path hidden by pruning does not make the displayed map connected. Use `scripts/validate_dependency_graph.py` with the schemas in the evidence reference; it checks structure and consistency, not source truth. Cycles claiming equivalence still need manual source review.

## 5. Verify visible conclusions

Re-open the original statement before writing any key node. Do not rely on an introduction paraphrase when the formal theorem is available.

For every highlighted theorem or corollary, check:

- quantifiers and existence statements;
- hypotheses, including regularity, zero-mean, irrationality, ergodicity, and parameter ranges;
- normalization factors and residue-class restrictions;
- uniformity clauses;
- subsequences, nonvanishing/rationality assumptions, shared normalizations, and strict versus non-strict bounds;
- whether nonconvergence, failure of equidistribution, or failure of an orthogonality property is the actual conclusion.

Use the source language for theorem/proposition/lemma text unless the user requests translation. Localize Section-stage headings only if useful. Bold result identifiers; bold only genuinely key conclusions. Keep formulas at normal math weight.

## 6. Draft the Mermaid proof skeleton

Use Mermaid when it helps review a complex proof skeleton. A small or already specified layout may be implemented directly from the evidence ledger; no separate layout approval is required unless requested.

1. Show the curated main proof; keep completeness in the ledger.
2. Use subgraphs for proof modules, not merely chapter boundaries.
3. Use exact result type and number plus a short mathematical phrase.
4. Expand visible acronyms at first use.
5. Branch shared inputs explicitly.
6. Preserve parallel branches and whitespace.
7. Label complementary cases differently from alternatives.

Treat reviewed Mermaid geometry as a layout contract for TikZ.

Review can be local; do not add an approval stop unless the user requests one. If parallel extraction helps, give each proof module shared IDs/evidence fields and separate output ownership; reconcile numbering and cross-module edges before one author builds the final map.

## 7. Design and draw the theorem map

For a finished figure, read [references/theorem-map-figure-production.md](references/theorem-map-figure-production.md) and write a short design brief before editing TikZ.

Use this semantic encoding unless the user requests another:

- solid dark arrow: direct dependency;
- thin gray arrow: technical input;
- dashed colored arrow: complementary case or alternative, named in the legend;
- dotted gray arrow: implication or specialization;
- low-saturation neutral band: context.

Prefer functional color zones over theorem-type colors. Keep formal result kinds explicit in text. Use long dedicated rails for cross-zone edges. Merge several prerequisites at a visible gate when that gate is mathematically justified.

Lay out the final text using the **rendered box heights**, including wrapping and mathematics. A minimum height is not a maximum height. Prefer relative positioning or row envelopes to fixed center-to-center spacing. When boxes touch, increase row spacing and canvas height before shrinking fonts. Wider parallel branches may need a wider canvas; no example paper size is mandatory.

Use [assets/theorem-dependency-four-zone.tex](assets/theorem-dependency-four-zone.tex) only for a genuine four-stage top-to-bottom architecture. For parallel branches with unequal box heights, [assets/theorem-dependency-three-branch.tex](assets/theorem-dependency-three-branch.tex) demonstrates relative placement and a measured row envelope. Neither template is a required topology; preserve the evidence-backed layout.

Do not print workflow notes, provenance chatter, or semantic-audit language inside the figure. A subtitle is off by default; include one only when it adds mathematical information not already present in the title or legend.

## 8. Compile and visually validate

Resolve `SKILL_ROOT` to the directory containing this `SKILL.md`. Run bundled scripts by absolute path; do not assume the project working directory is the skill directory and do not depend on another skill’s files:

```powershell
python "$SKILL_ROOT/scripts/tikz-validator.py" figure.tex
xelatex -no-pdf -interaction=nonstopmode -halt-on-error figure.tex
xdvipdfmx -o figure.pdf figure.xdv
pdftoppm -png -r 180 -singlefile figure.pdf figure-preview
pdfinfo figure.pdf
python "$SKILL_ROOT/scripts/pdf-overlap-checker.py" figure.pdf --json
```

For a machine-readable inventory and edge ledger, also run:

```powershell
python "$SKILL_ROOT/scripts/validate_dependency_graph.py" dependency-nodes.json dependency-edges.csv --tex figure.tex --conclusion main-result
```

Before the overlap checker, verify `pdfplumber` and PyMuPDF (`fitz`) in the selected interpreter. Prefer an existing configured runtime; a missing module in the default Python does not mean no suitable runtime exists. Install only if needed and authorized by the environment. Missing dependencies or skipped geometry checks mean incomplete validation, never a pass. Adapt executable paths to the environment. On Windows, follow the project's XeLaTeX/XDVIPDFMX workflow and existing permission requirements.

Inspect the LaTeX log for `Overfull`, `Underfull`, `Missing character`, and font substitution warnings. Logs do not detect TikZ node overlap reliably; always inspect the rendered PNG.

After every material layout change:

1. rerun the coordinate validator;
2. compile the vector PDF;
3. render a whole-page PNG;
4. inspect title, legend, stage headers, node borders, formulas, routes, and page boundaries;
5. triage overlap-checker output against the PNG;
6. iterate until no real blocker remains.

Static TikZ checks are approximate and must report unsupported transforms/styles instead of pretending to cover them. PDF geometry is the rendered check. Fraction bars, integral limits, `liminf`/`limsup` subscripts, and simultaneous subscript/superscript boxes can generate candidates. Use the reported page and bounding boxes for local inspection; do not globally suppress mathematical symbols or describe an unresolved candidate as passed. Keep automated findings and manual dispositions distinct in `figure-qa.md`.

For dense or original layouts, an isolated review can help when delegation is authorized. Select reviewers for concrete unresolved risks, provide the raw current artifact, and repeat only the checks affected by material fixes. Absence of subagents does not block a documented local review.

## Quality gates

Do not claim completion until all are true:

- every visible edge has evidence and a relation class;
- every highlighted conclusion was checked against the original statement;
- theorem numbering and aliases match the rendered source;
- the layout agrees with the evidence-backed proof skeleton;
- exclusions and grouped nodes are documented;
- complete and visible graph checks agree with the actual displayed arrows;
- Section headers align and are unobstructed;
- theorem identifiers and key conclusions use consistent emphasis;
- the smallest text remains readable at intended print size;
- TikZ compiles without missing characters or overflow warnings;
- the PDF is nonzero, opens normally, has the expected page size/count, and remains vector;
- custom page dimensions and smallest font size are reported accurately; validation covers every delivered figure page;
- PNG inspection confirms no real overlap, clipping, route-through-text, or misleading empty region;
- the final result and its evidence ledger agree.

## Scope discipline

When evidence is incomplete, deliver a partial graph with explicit gaps. Never manufacture connectivity. When the user requests only analysis, stop after the ledger and graph specification; do not create figure files unless asked.
