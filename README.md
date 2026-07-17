<p align="right">
  <a href="README.md"><img alt="English" src="https://img.shields.io/badge/Language-English-2563EB"></a>
  <a href="README_zh-CN.md"><img alt="简体中文" src="https://img.shields.io/badge/语言-简体中文-D93F0B"></a>
</p>

# Map Theorem Dependencies

A Codex skill for extracting, verifying, and visualizing theorem-level logical dependencies in mathematical papers, theses, books, and LaTeX/Markdown/PDF projects.

It treats every dependency edge as a mathematical claim that needs textual evidence. The workflow produces a reader-reviewable Mermaid proof skeleton before turning the approved structure into a publication-ready TikZ/PDF figure.

## What it does

- inventories theorems, propositions, lemmas, corollaries, definitions, and named results;
- records exact identifiers, aliases, source locations, proof spans, and logical roles;
- distinguishes direct dependencies, technical inputs, implications, alternative routes, and contextual relationships;
- works backward from the main conclusions to recover the proof spine;
- presents a concise Mermaid diagram for semantic and layout review;
- preserves the approved Mermaid geometry when producing TikZ;
- validates theorem numbering, edge direction, visual routing, typography, and rendered output.

## Core principles

1. **Evidence before edges.** A thematic connection is not automatically a proof dependency.
2. **Mermaid before TikZ.** Review the mathematical structure and natural layout before publication typesetting.
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
6. Write a figure design brief based on the approved topology.
7. Produce the TikZ/PDF/PNG figure with the companion figure skill.
8. Perform semantic and visual audits.

## Expected outputs

| Artifact | Purpose |
|---|---|
| `dependency-ledger.md` or `.csv` | Result inventory, statements, locations, aliases, and roles |
| `dependency-edges.csv` | Evidence-backed edges, relation classes, and confidence |
| `dependency-draft.md` or Mermaid diagram | Reader-reviewable main-proof skeleton |
| Standalone `.tex`, vector `.pdf`, and `.png` | Publication-ready dependency figure |
| `dependency-audit.md` | Exclusions, grouping decisions, uncertainties, and validation results |

## Visual semantics

- **Solid dark arrow:** direct proof dependency
- **Thin gray arrow:** technical input
- **Emphasized dashed arrow:** alternative proof route
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
cp -R map-theorem-dependencies/agents map-theorem-dependencies/assets map-theorem-dependencies/references \
  "${CODEX_HOME:-$HOME/.codex}/skills/map-theorem-dependencies/"
```

The final TikZ production stage uses the companion `$thesis-figure-skill`. XeLaTeX and Poppler are recommended when compiling and visually checking PDF deliverables.

## Usage

Invoke the skill in Codex with a mathematical source project:

```text
Use $map-theorem-dependencies to analyze the theorem dependencies in this paper,
show me the Mermaid proof skeleton first, and create a TikZ/PDF map after approval.
```

If only analysis is requested, the skill stops after the ledger and graph specification instead of creating files automatically.

## Repository structure

```text
map-theorem-dependencies/
├── SKILL.md
├── README.md
├── README_zh-CN.md
├── agents/
│   └── openai.yaml
├── assets/
│   └── theorem-dependency-four-zone.tex
└── references/
    └── dependency-evidence.md
```
