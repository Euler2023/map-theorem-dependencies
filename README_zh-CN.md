<p align="right">
  <a href="README.md"><img alt="English" src="https://img.shields.io/badge/Language-English-2563EB"></a>
  <a href="README_zh-CN.md"><img alt="简体中文" src="https://img.shields.io/badge/语言-简体中文-D93F0B"></a>
</p>

# 定理依赖关系图

这是一个用于 Codex 的技能，负责从数学论文、学位论文、专著以及 LaTeX、Markdown 或 PDF 项目中提取、核验并可视化定理层面的逻辑依赖关系。

它把每一条依赖边都视为需要文本证据支持的数学断言。工作流会先生成便于读者审阅的 Mermaid 主证明骨架，待结构和布局确认后，再制作可发表的 TikZ/PDF 图。

## 主要功能

- 盘点定理、命题、引理、推论、定义和具名结果；
- 记录准确编号、编号别名、来源位置、证明区间和逻辑角色；
- 区分直接依赖、技术输入、逻辑推出、替代路线和背景关系；
- 从主要结论向前回溯，恢复主证明骨架；
- 先提交简洁的 Mermaid 图，供语义和布局审阅；
- 制作 TikZ 时保留已确认的 Mermaid 几何关系；
- 核验定理编号、箭头方向、走线、字体和最终渲染结果。

## 核心原则

1. **先取证，后连边。** 主题相关不等于证明依赖。
2. **先 Mermaid，后 TikZ。** 先确认数学结构和自然布局，再进行出版级排版。
3. **使用面向读者的标签。** 缩写首次出现时展开全称，不显示内部模块编号。
4. **按功能使用颜色。** 颜色表示证明模块和逻辑角色，不表示定理类型。
5. **保留必要留白。** 优先扩大画布，不通过缩小字体或强塞分栏来压缩分支结构。
6. **分析与成品分离。** 审计信息写入审计文件，不放进最终配图。

## 工作流程

1. 确定资料来源的优先级。
2. 建立完整的结果清单。
3. 提取有证据支持的依赖边。
4. 恢复经过筛选的主证明骨架。
5. 起草并审阅 Mermaid 依赖图。
6. 根据审定拓扑编写配图设计说明。
7. 配合论文配图技能生成 TikZ、PDF 和 PNG。
8. 完成语义审计和视觉审计。

## 预期成果

| 文件 | 用途 |
|---|---|
| `dependency-ledger.md` 或 `.csv` | 结果清单、陈述摘要、位置、编号别名和角色 |
| `dependency-edges.csv` | 有证据支持的依赖边、关系类型和置信度 |
| `dependency-draft.md` 或 Mermaid 图 | 供读者审阅的主证明骨架 |
| 独立 `.tex`、矢量 `.pdf` 和 `.png` | 可发表的定理依赖图 |
| `dependency-audit.md` | 排除项、分组决定、不确定边和验证结果 |

## 视觉语义

- **深色实线箭头：** 直接证明依赖
- **灰色细箭头：** 技术输入
- **强调虚线箭头：** 替代证明路线
- **灰色点线箭头：** 推论、特化或推广
- **灰蓝色框：** 技术性或辅助性输入
- **模块颜色：** 所属证明分支
- **较强边框或填充：** 分支结论或引言中的主要结果

结果的正式类型——定理、命题、引理或推论——仍由节点文字明确标注。

## 安装

克隆仓库，然后只把技能包文件复制到 Codex 技能目录：

```bash
git clone https://github.com/Euler2023/map-theorem-dependencies.git
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills/map-theorem-dependencies"
cp map-theorem-dependencies/SKILL.md "${CODEX_HOME:-$HOME/.codex}/skills/map-theorem-dependencies/"
cp -R map-theorem-dependencies/agents map-theorem-dependencies/assets map-theorem-dependencies/references \
  "${CODEX_HOME:-$HOME/.codex}/skills/map-theorem-dependencies/"
```

最终 TikZ 制作阶段会调用配套的 `$thesis-figure-skill`。如需编译并检查 PDF，建议安装 XeLaTeX 和 Poppler。

## 使用示例

在 Codex 中对数学资料项目调用该技能：

```text
使用 $map-theorem-dependencies 分析这篇论文中各定理之间的依赖关系，
先给我看 Mermaid 主证明骨架，确认后再生成 TikZ/PDF 图。
```

如果用户只要求分析，技能会在完成结果清单和图结构说明后停止，不会自动创建文件。

## 仓库结构

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
