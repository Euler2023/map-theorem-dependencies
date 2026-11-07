# Theorem-map figure production

Use this reference only when producing or revising a finished TikZ/PDF theorem dependency map.

## 1. Page planning

- Choose the canvas from the graph topology, not from a default paper size.
- A single vertical spine can start at A4 width (210 mm); independent parallel branches may require a wider canvas. Use 7–10 mm side margins.
- Test 297 mm height, but do not force a dense map into standard A4. Increase to a custom 210 × H mm long page before shrinking fonts.
- Record the actual size from `pdfinfo`; “A4-width long page” is not standard A4.
- Prefer one readable vector page over a nominal A4 page with 7–8 pt text.
- Choose dimensions for the current graph, not the preceding example. Do not reuse a previous layout's dimensions as a universal default. If standard print size is a user constraint, use a readable overview plus detail pages rather than an oversized page silently reduced to unreadable type.

Recommended minimums:

- ordinary nodes: 9.5 pt;
- key intermediate results: 11 pt;
- headline conclusions: 12.5 pt;
- ordinary line spacing: roughly 1.15–1.2 × font size.

## 2. Layout grammar

### Measure content before spacing rows

Set the final node text, font, math, text width, and padding before placing lower rows. Wrapping can turn four intended lines into seven; fractions, sums, and display limits also increase height. `minimum height` is only a lower bound. Never interpret a static validator's 0.9 cm estimate or a clean TeX overflow log as a measured height.

For a sequential branch, use TikZ `positioning` and `below=8mm of predecessor` or an equivalent measured-anchor calculation. For parallel rows, enclose the **whole rendered row** in an invisible `fit` node and position the next row below that envelope. Start arrows at real anchors. Keep explicit coordinates in physical units where practical; axis `x/y` scaling changes coordinates but does not automatically scale text boxes. `scale`/`transform shape` has different effects and must not be used as a substitute for planning readable typography.

When frames touch, lengthen the canvas and the affected rows, keeping the font stable. Enlarge width only when parallel branches or line wrapping need it. Add enough height for the tallest formula, not just a uniform percentage applied to center coordinates. Avoid global regular-expression replacement of `(x,y)` strings in TeX: mathematical tuples and relative offsets can match the same pattern.

See [../assets/theorem-dependency-three-branch.tex](../assets/theorem-dependency-three-branch.tex) for a measured-height parallel-branch starter. Its unnumbered example nodes and edges are layout placeholders, not source evidence.

### Route around content

- Use top-to-bottom stages for a proof roadmap with sequential Sections.
- Give every stage header the same anchor, width, padding, and text alignment.
- Keep stage capsules on a common left edge and prevent tall nodes from covering their ends.
- Route long cross-stage dependencies on dedicated side rails.
- Use open curves or separated branches for complementary cases; avoid two dashed L-paths that visually close into an empty rectangle.
- Do not let opposite arrows share the same segment and form a false bidirectional knot.
- Reserve a separate exit anchor/rail for a box receiving an arrow on its left. Reusing its left-entry segment for an outgoing arrow can make unrelated dependencies appear bidirectional.
- A long vertical connector must avoid every intervening box and header, not only its source and target. Case labels belong next to the rail or curve; a white label patch hiding an arrow is not a routing fix.
- Center final conclusions on the page axis.
- For a counterexample branch, balance the construction row, the final-specialization node, and the final theorem vertically. Avoid an isolated small node in one lower corner that creates a large asymmetric void.
- Treat a visible empty region larger than roughly 3 × 2 cm as a layout question: it may be legitimate branch separation, but must not look accidental.

## 3. Text and mathematics

- Default to the original language for theorem/proposition/lemma boxes.
- Section-stage titles may be localized.
- Bold exact identifiers such as `Theorem 8.1` and `Proposition 6.1`.
- Bold the conclusion text only for genuinely key results.
- Use a matching OpenType text/math pair, for example TeX Gyre Termes plus TeX Gyre Termes Math.
- Do not apply global bold to a node containing a long formula. Bold textual emphasis explicitly and leave the formula at normal math weight.
- Write enough of the final conclusion to identify what is proved: quantifier, object, limiting statement, uniformity, failure, or nonconvergence.
- A subtitle is off by default. The title and compact relation legend are normally sufficient.
- Inspect mathematics inside wide centered boxes. If relation spacing stretches excessively, fixed `\thinmuskip=3mu`, `\medmuskip=4mu`, and `\thickmuskip=5mu` can stabilize it. Apply this only when the rendered result needs it; preserve readable formula spacing.

## 4. Density and grouping

- Keep every displayed result identifier reader-reviewable.
- Group lemmas only when the ledger records every member and the group has a single shared function.
- If one grouped member has an extra outgoing dependency, expose that edge explicitly or split the member out.
- Do not hide principal-character, small-/large-modulus, exceptional-set, or final-specialization inputs merely to simplify the drawing.
- Use a concise “gate” node only when it represents an actual assembly step, not a decorative funnel.

## 5. Compile loop

Before running the overlap checker, verify that its Python interpreter provides `pdfplumber` and PyMuPDF (`fitz`). Prefer an already configured runtime, including a project environment or bundled runtime. Install packages only if needed and authorized; do not silently skip line-through-node or node-overlap checks. Reusing a known pure-Python package directory can be appropriate after import verification, but do not mix incompatible binary packages across Python versions.

On Windows, a robust workflow is:

1. run XeLaTeX with `-no-pdf` and `-halt-on-error`;
2. confirm a complete `.xdv` and clean log;
3. run `xdvipdfmx` to produce the vector PDF;
4. use `pdfinfo` to check page size, count, and nonzero output;
5. render the whole page with `pdftoppm` at 180–300 dpi;
6. view the PNG at original resolution.

The log can reveal overflow, missing glyphs, and font warnings. It cannot reliably reveal TikZ box-box overlap, arrow-through-text, blocked stage headers, or misleading whitespace.

Static coordinate checking is a heuristic. Read its coverage warnings for macros, named styles, transforms, and unmeasured heights. A warning about a short adjacent arrow or a long dedicated rail may be harmless; a heuristic must not force a worse layout. The rendered PDF geometry and PNG decide whether there is a real collision. Do not describe a heuristic-only run as complete visual validation.

The bundled static preflight supports literal numeric coordinates (including leading decimals), scalar `x/y` bases and literal node sizes; it is not a TeX interpreter. `coverage` means the affected geometry was not checked; `node-metrics` means the size is a minimum or estimate requiring rendering. Legal diagonals and dedicated detour rails are accepted by default. Optional end-of-command contracts such as `% tikz-validator: orthogonal` or `edge-gap` enable narrowly scoped route checks; see the script's usage text. Exit 0 means no candidate was found in its supported subset, not that the rendered diagram passed.

`pdf-overlap-checker.py` exits 2 for incomplete checks or error-level candidates, 1 for warning-only candidates, and 0 when no candidates were found. Its JSON still requires visual review; mathematical ink is not established by word bounding boxes. `--max-per-category` limits only the human-readable examples, never the structured report.

## 6. Visual review

Inspect in this order:

1. Three-second impression: title, stage flow, and final theorem are immediately apparent.
2. Main proof path: trace arrows from foundations to conclusions without guessing.
3. Stage headers: same left edge and width, complete and unobstructed.
4. Nodes: no border contact, clipping, or text collision.
5. Formulas: integral limits, sums, subscripts, and superscripts are legible.
6. Edges: arrow direction matches dependency direction; no route crosses unrelated text.
7. Counterexample branch: visually centered and free of accidental blank corners.
8. Page: safe print margins and no content outside the stage background.

Run the bundled overlap checker after compiling. Treat its output as coordinates for inspection, not as ground truth. Fix real text overlap and route-through-text first; document glyph-box false positives.

### Triage without losing detection coverage

- Keep the full structured report. Use page/bounding-box locations to render only the flagged region when needed; use grouped summaries to navigate repeated warnings.
- Fractions such as 3/2 or 1/2, integral limits, `liminf`/`limsup` subscripts, and simultaneous super/subscripts often have overlapping conservative glyph boxes. A fraction bar can also trigger text-line detection. Inspect actual ink before classifying them.
- A bounding-box candidate is unresolved until inspected; do not suppress a category globally just because some formulas are valid. Keep true node overlap, line-through-node, and clipped text detectable.
- Distinguish automated status from manual disposition: record category, page/region, observed result, and action (`fixed`, `glyph-box false positive`, or `unresolved`). If all remaining candidates are inspected false positives, say so; do not rewrite the raw checker output into a zero-error pass.
- Missing libraries, an unreadable/empty PDF, or unexamined pages are incomplete checks. Inspect every delivered figure page. An extraction-only audit does not need to grow into a full independent proof verification.

## 7. Revision priorities

Use this order:

1. correct mathematical meaning and missing edges;
2. remove real overlap and clipping by increasing row separation/canvas height as needed;
3. reroute ambiguous branches and clear headers;
4. enlarge width or divide a constrained print layout when topology requires it;
5. rebalance whitespace;
6. only then reduce font size, and never below the intended print minimum.

After a user-requested visual change, re-render the whole page. A local coordinate edit can create a distant collision through long rails or changed node dimensions.
