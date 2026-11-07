<p align="right">
  <a href="README.md"><img alt="English" src="https://img.shields.io/badge/Language-English-2563EB"></a>
  <a href="README_zh-CN.md"><img alt="简体中文" src="https://img.shields.io/badge/语言-简体中文-D93F0B"></a>
</p>

# 定理依赖关系图

这是一个用于 Codex 的技能，负责从数学论文、学位论文、专著以及 LaTeX、Markdown 或 PDF 项目中提取、核验并可视化定理层面的逻辑依赖关系。

它把每一条依赖边都视为需要原文证据支持的断言，先恢复证明骨架，再按用户要求制作可读的TikZ/PDF/PNG图。复杂结构可以先用Mermaid审阅；只有用户要求时才增加单独的审批停顿。恢复原文论证不等于独立确认主定理正确。

## 主要功能

- 盘点定理、命题、引理、推论、定义和具名结果；
- 记录准确编号、编号别名、来源位置、证明区间和逻辑角色；
- 区分直接依赖、技术输入、逻辑推出、互补情形、替代路线和背景关系；
- 从主要结论向前回溯，恢复主证明骨架；
- 先提交简洁的 Mermaid 图，供语义和布局审阅；
- 制作TikZ时保留已审阅的证明拓扑；
- 分别检查完整账本与主图中可见的依赖子图；
- 按实际文本框高度布置后续行，优先增高画布而非缩小字号；
- 核验定理编号、箭头方向、走线、字体和最终渲染结果。

## 核心原则

1. **先取证，后连边。** 主题相关不等于证明依赖。
2. **先结构，后排版。** 先核对有证据的证明拓扑，小图可以直接进入TikZ，不强制增加Mermaid审批。
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
7. 用本技能内置资源独立生成TikZ、PDF和PNG。
8. 完成语义审计和视觉审计。

## 预期成果

| 文件 | 用途 |
|---|---|
| `dependency-ledger.md` 或 `.csv` | 结果清单、陈述摘要、位置、编号别名和角色 |
| `dependency-edges.csv` | 有证据支持的依赖边、关系类型和置信度 |
| `dependency-draft.md` 或 Mermaid 图 | 供读者审阅的主证明骨架 |
| 独立 `.tex`、矢量 `.pdf` 和 `.png` | 可发表的定理依赖图 |
| `dependency-audit.md` | 排除项、分组决定、不确定边和验证结果 |
| 可机读节点清单与语义报告 | 完整/可见图检查、选定结论和明确的覆盖限制 |
| `figure-qa.md` | 实际纸张尺寸、字号、几何候选及目视处置 |

## 视觉语义

- **深色实线箭头：** 直接证明依赖
- **灰色细箭头：** 技术输入
- **带标签虚线箭头：** 互补情形或替代路线，在标签/图例中明确区分
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
cp -R map-theorem-dependencies/agents map-theorem-dependencies/assets map-theorem-dependencies/references map-theorem-dependencies/scripts \
  "${CODEX_HOME:-$HOME/.codex}/skills/map-theorem-dependencies/"
```

本技能已经自包含：内置脚本可校验 TikZ 坐标并检查 PDF 几何关系，无需调用其他制图技能。编译与渲染建议安装 XeLaTeX 和 Poppler；运行 PDF 重叠检查器时，请安装 `scripts/requirements.txt` 中列出的 Python 包。

## 验证

使用Python 3.10及以上版本；PDF检查及其回归测试还需 `scripts/requirements.txt` 中列出的依赖。

```bash
python scripts/validate_dependency_graph.py nodes.json edges.csv --tex figure.tex --conclusion main-result
python scripts/tikz-validator.py figure.tex
python scripts/pdf-overlap-checker.py figure.pdf --json
python -m unittest discover -s scripts -p 'test_*.py'
```

语义脚本检查数据和声明的`% EDGE`注释，不证明数学断言，也不完整解析任意TikZ代码。静态几何检查会报告其不支持的语法；PDF检查覆盖全部页面，为候选附页码和区域坐标，供局部目视复核。候选不自动等于错误，也不等于通过；缺少几何依赖时明确返回未完成。字段、退出状态与误报处置见两个参考文件。

## 使用示例

在 Codex 中对数学资料项目调用该技能：

```text
使用 $map-theorem-dependencies 分析这篇论文中各定理之间的依赖关系，
先给我看 Mermaid 主证明骨架，确认后再生成 TikZ/PDF 图。
```

如果用户只要求分析，技能会在完成结果清单和图结构说明后停止；只有要求成图时才生成最终图文件。

## 仓库结构

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
