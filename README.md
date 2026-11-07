<p align="right">
  <a href="README.md"><img alt="English" src="https://img.shields.io/badge/Language-English-2563EB"></a>
  <a href="README_zh-CN.md"><img alt="简体中文" src="https://img.shields.io/badge/语言-简体中文-D93F0B"></a>
</p>

# Map Theorem Dependencies

A Codex skill for extracting, verifying, and visualizing theorem-level logical dependencies in mathematical papers, theses, books, and LaTeX/Markdown/PDF projects.

It treats every dependency edge as a claim requiring source evidence. It recovers a proof skeleton and, when requested, produces a readable TikZ/PDF/PNG map. Mermaid is useful for complex layouts; a separate approval stop is needed only when the user asks for one. Mapping a source's argument does not independently certify its main theorem.

## What it does

- inventories theorems, propositions, lemmas, corollaries, definitions, and named results;
- records exact identifiers, aliases, source locations, proof spans, and logical roles;
- distinguishes direct dependencies, technical inputs, implications, complementary cases, alternative routes, and context;
- works backward from the main conclusions to recover the proof spine;
- presents a concise Mermaid diagram for semantic and layout review;
- preserves the reviewed proof topology when producing TikZ;
- validates both the complete ledger and the curated visible graph;
- places unequal-height boxes using measured anchors and grows the canvas before shrinking text;
- validates theorem numbering, edge direction, visual routing, typography, and rendered output.

## Core principles

1. **Evidence before edges.** A thematic connection is not automatically a proof dependency.
2. **Structure before typesetting.** Review the evidence-backed topology before arranging the figure; Mermaid is optional for small maps.
3. **Reader-facing labels.** Expand abbreviations at first appearance and never expose internal module IDs.
4. **Color by function.** Colors represent proof modules and logical roles, not theorem types.
5. **Preserve whitespace.** Increase the canvas before shrinking fonts or compressing a branching proof into columns.
6. **Separate analysis from presentation.** Audit details belong in the audit file, not in the finished figure.

## Workflow

1. Establish the source hierarchy.
2. Build a complete result inventory.
3. Extract evidence-backed dependency edges.
4. Recover the curated main-proof spine.
5. Draft and review the Mermaid dependency map.
6. Write a figure design brief based on the reviewed topology.
7. Produce the TikZ/PDF/PNG figure using this skill's bundled resources.
8. Perform semantic and visual audits.

## Expected outputs

| Artifact | Purpose |
|---|---|
| `dependency-ledger.md` or `.csv` | Result inventory, statements, locations, aliases, and roles |
| `dependency-edges.csv` | Evidence-backed edges, relation classes, and confidence |
| `dependency-draft.md` or Mermaid diagram | Reader-reviewable main-proof skeleton |
| Standalone `.tex`, vector `.pdf`, and `.png` | Publication-ready dependency figure |
| `dependency-audit.md` | Exclusions, grouping decisions, uncertainties, and validation results |
| Machine-readable nodes and semantic report | Full/visible graph checks, selected conclusions, and explicit coverage limits |
| `figure-qa.md` | Actual page dimensions, font sizes, geometry findings and visual dispositions |

## Visual semantics

- **Solid dark arrow:** direct proof dependency
- **Thin gray arrow:** technical input
- **Labeled dashed arrow:** complementary case or alternative route, distinguished in the label/legend
- **Dotted gray arrow:** implication, specialization, or generalization
- **Neutral gray-blue box:** technical or auxiliary input
- **Module color:** membership in a proof branch
- **Strong border/fill:** branch conclusion or introduction-level result

The result type—Theorem, Proposition, Lemma, or Corollary—remains explicit in the node text.

## Installation

Clone the repository, then copy only the skill package files into your Codex skills directory:

```bash
git clone https://github.com/Euler2023/map-theorem-dependencies.git
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills/map-theorem-dependencies"
cp map-theorem-dependencies/SKILL.md "${CODEX_HOME:-$HOME/.codex}/skills/map-theorem-dependencies/"
cp -R map-theorem-dependencies/agents map-theorem-dependencies/assets map-theorem-dependencies/references map-theorem-dependencies/scripts \
  "${CODEX_HOME:-$HOME/.codex}/skills/map-theorem-dependencies/"
```

The skill is self-contained: its bundled scripts validate TikZ coordinates and inspect PDF geometry without invoking another figure skill. XeLaTeX and Poppler are recommended for compilation and rendering; install the Python packages listed in `scripts/requirements.txt` when running the PDF overlap checker.

## Validation

Use Python 3.10 or newer; PDF checks and their regression tests also need the packages in `scripts/requirements.txt`.

```bash
python scripts/validate_dependency_graph.py nodes.json edges.csv --tex figure.tex --conclusion main-result
python scripts/tikz-validator.py figure.tex
python scripts/pdf-overlap-checker.py figure.pdf --json
python -m unittest discover -s scripts -p 'test_*.py'
```

The semantic checker audits data and declared `% EDGE` comments, not proof truth or arbitrary TikZ code. Static geometry is approximate and reports unsupported syntax. The PDF checker inspects all pages, reports page/bounding-box locations and retains candidates for local visual review; a candidate is not an automatic defect or a pass. Missing geometry dependencies produce an incomplete result. See the two references for schemas, exit statuses, and triage.

## Usage

Invoke the skill in Codex with a mathematical source project:

```text
Use $map-theorem-dependencies to analyze the theorem dependencies in this paper,
show me the Mermaid proof skeleton first, and create a TikZ/PDF map after approval.
```

If only analysis is requested, the skill stops after the ledger and graph specification; finished figure files require a figure request.

## Repository structure

```text
map-theorem-dependencies/
├── SKILL.md
├── README.md
├── README_zh-CN.md
├── agents/
│   └── openai.yaml
├── assets/
│   ├── theorem-dependency-four-zone.tex
│   └── theorem-dependency-three-branch.tex
├── references/
│   ├── dependency-evidence.md
│   └── theorem-map-figure-production.md
└── scripts/
    ├── validate_dependency_graph.py
    ├── tikz-validator.py
    ├── pdf-overlap-checker.py
    ├── requirements.txt
    └── test_*.py
```
