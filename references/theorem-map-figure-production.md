# Theorem-map figure production

Use this reference only when producing or revising a finished TikZ/PDF theorem dependency map.

## 1. Page planning

- Choose the canvas from the graph topology, not from a default paper size.
- Start with A4 width (210 mm) for a vertical reading path. Use 7–10 mm side margins.
- Test 297 mm height, but do not force a dense map into standard A4. Increase to a custom 210 × H mm long page before shrinking fonts.
- Record the actual size from `pdfinfo`; “A4-width long page” is not standard A4.
- Prefer one readable vector page over a nominal A4 page with 7–8 pt text.

Recommended minimums:

- ordinary nodes: 9.5 pt;
- key intermediate results: 11 pt;
- headline conclusions: 12.5 pt;
- ordinary line spacing: roughly 1.15–1.2 × font size.

## 2. Layout grammar

- Use top-to-bottom stages for a proof roadmap with sequential Sections.
- Give every stage header the same anchor, width, padding, and text alignment.
- Keep stage capsules on a common left edge and prevent tall nodes from covering their ends.
- Route long cross-stage dependencies on dedicated side rails.
- Use open curves or separated branches for complementary cases; avoid two dashed L-paths that visually close into an empty rectangle.
- Do not let opposite arrows share the same segment and form a false bidirectional knot.
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

## 4. Density and grouping

- Keep every displayed result identifier reader-reviewable.
- Group lemmas only when the ledger records every member and the group has a single shared function.
- If one grouped member has an extra outgoing dependency, expose that edge explicitly or split the member out.
- Do not hide principal-character, small-/large-modulus, exceptional-set, or final-specialization inputs merely to simplify the drawing.
- Use a concise “gate” node only when it represents an actual assembly step, not a decorative funnel.

## 5. Compile loop

Before running the overlap checker, verify that its Python interpreter provides `pdfplumber` and PyMuPDF (`fitz`). Prefer the workspace-bundled Python when available. If either import is missing, report the missing check explicitly and request permission before installing packages; do not silently skip line-through-node or node-overlap checks.

On Windows, a robust workflow is:

1. run XeLaTeX with `-no-pdf` and `-halt-on-error`;
2. confirm a complete `.xdv` and clean log;
3. run `xdvipdfmx` to produce the vector PDF;
4. use `pdfinfo` to check page size, count, and nonzero output;
5. render the whole page with `pdftoppm` at 180–300 dpi;
6. view the PNG at original resolution.

The log can reveal overflow, missing glyphs, and font warnings. It cannot reliably reveal TikZ box-box overlap, arrow-through-text, blocked stage headers, or misleading whitespace.

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

## 7. Revision priorities

Use this order:

1. correct mathematical meaning and missing edges;
2. remove real overlap and clipping;
3. reroute ambiguous branches;
4. enlarge or lengthen the canvas;
5. rebalance whitespace;
6. only then reduce font size, and never below the intended print minimum.

After a user-requested visual change, re-render the whole page. A local coordinate edit can create a distant collision through long rails or changed node dimensions.
