#!/usr/bin/env python3
r"""Conservative preflight for a literal subset of TikZ, not a TeX interpreter.

Usage: python tikz-validator.py figure.tex
Exit codes: 0 = no candidates in the supported subset, 1 = review/coverage
warnings, 2 = detected input error. Rendered PDF checks remain mandatory.

Supported geometry: literal numeric positions (including .7 and -.5), scalar
x/y bases in cm/mm/in/pt/bp, nested scopes with these bases, and literal
rectangle-node dimensions/cardinal anchors. Coordinates are converted to cm;
node dimensions do NOT inherit x/y coordinate units. Named styles/macros,
vector bases, transforms, calculated/relative positions and nonrectangular
shapes are not expanded: affected geometry is skipped with coverage warnings.
Node sizes are declared minima or text-layout ESTIMATES, not measured bounds.
Explicit line breaks increase the height estimate and trigger a render warning.
Wrapping, math, fonts and TeX boxes require rendered verification.

Diagonals and detours are legal. Optional route contracts are enabled by an
end-of-command comment (not a TikZ key):
  % tikz-validator: orthogonal
  % tikz-validator: monotone-x
  % tikz-validator: monotone-y
  % tikz-validator: edge-gap
The first three require complete literal numeric -- paths. edge-gap checks
only one straight segment with explicit facing cardinal node anchors. There
is no default maximum-edge-length or inferred route-direction rule.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
COORD_PATTERN = re.compile(rf"\(\s*({NUMBER})\s*,\s*({NUMBER})\s*\)")
LENGTH_PATTERN = re.compile(rf"\s*({NUMBER})\s*(cm|mm|in|pt|bp)\s*\Z")
UNITS_CM = {"cm": 1., "mm": .1, "in": 2.54, "pt": 2.54 / 72.27, "bp": 2.54 / 72}
COMMAND_PATTERN = re.compile(r"\\(?:node|draw|fill)\b|\\(?:begin|end)\s*\{(?:tikzpicture|scope)\}")
VISUAL_KEYS = {
    "draw", "fill", "color", "text", "opacity", "fill opacity", "draw opacity",
    "line width", "rounded corners", "align", "font", "thick", "thin", "very thick",
    "very thin", "ultra thick", "ultra thin", "solid", "dashed", "dotted",
    "densely dashed", "densely dotted", "loosely dashed", "loosely dotted",
    "rectangle", "name", "overlay", "remember picture", "baseline",
}
NODE_KEYS = {
    "minimum width", "minimum height", "text width", "inner sep", "inner xsep",
    "inner ysep", "outer sep", "outer xsep", "outer ysep", "anchor",
}
ANCHORS = {
    "center": (0, 0), "east": (1, 0), "west": (-1, 0), "north": (0, 1),
    "south": (0, -1), "north east": (1, 1), "north west": (-1, 1),
    "south east": (1, -1), "south west": (-1, -1),
}


@dataclass
class Point:
    x: float
    y: float


@dataclass
class Node:
    name: str
    x: float
    y: float
    width: float = 0.
    height: float = 0.
    text: str = ""
    line_no: int = 0
    group: int = 0
    geometry_ok: bool = True
    estimated: bool = False


@dataclass
class Zone:
    name: str
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    group: int = 0


@dataclass
class Issue:
    level: str
    category: str
    line_no: int
    message: str


@dataclass
class Context:
    x: float = 1.
    y: float = 1.
    geometry_ok: bool = True
    group: int = 0


@dataclass
class Draw:
    text: str
    line_no: int
    context: Context
    contracts: set[str] = field(default_factory=set)


@dataclass
class Scene:
    nodes: list[Node] = field(default_factory=list)
    zones: list[Zone] = field(default_factory=list)
    draws: list[Draw] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)


def strip_comments(content: str) -> str:
    """Remove comments preserving offsets; an odd backslash count escapes %."""
    chars = list(content)
    i = 0
    while i < len(content):
        if content[i] != "%":
            i += 1
            continue
        slashes, pos = 0, i - 1
        while pos >= 0 and content[pos] == "\\":
            slashes += 1
            pos -= 1
        if not slashes % 2:
            end = content.find("\n", i)
            end = end if end >= 0 else len(content)
            chars[i:end] = " " * (end - i)
            i = end
        else:
            i += 1
    return "".join(chars)


def read_group(text: str, pos: int, opening: str, closing: str) -> tuple[str, int]:
    if pos >= len(text) or text[pos] != opening:
        raise ValueError(f"expected {opening}")
    depth, braces, i = 1, 0, pos + 1
    while i < len(text):
        char = text[i]
        if char == "\\":
            i += 2
            continue
        if opening == "[":
            if char == "{":
                braces += 1
            elif char == "}":
                braces -= 1
        if not braces:
            if char == opening:
                depth += 1
            elif char == closing:
                depth -= 1
                if not depth:
                    return text[pos + 1:i], i + 1
        i += 1
    raise ValueError(f"unclosed {opening}")


def split_options(text: str) -> list[tuple[str, str | None]]:
    result, start, depth = [], 0, 0
    for i, char in enumerate(text + ","):
        if char in "{[(":
            depth += 1
        elif char in "}])":
            depth -= 1
        elif char == "," and depth == 0:
            item = text[start:i].strip()
            start = i + 1
            if item:
                key, sep, value = item.partition("=")
                result.append((re.sub(r"\s+", " ", key.strip()), value.strip() if sep else None))
    return result


def length_cm(text: str) -> float:
    match = LENGTH_PATTERN.fullmatch(text)
    if not match:
        raise ValueError(f"unsupported literal length: {text}")
    return float(match[1]) * UNITS_CM[match[2]]


def parse_draw_coords(line: str) -> list[Point]:
    return [Point(float(m[1]), float(m[2])) for m in COORD_PATTERN.finditer(line)]


def coverage(issues: list[Issue], line_no: int, message: str):
    issues.append(Issue("WARN", "coverage", line_no, message))


def command_options(text: str) -> tuple[str, int]:
    pos = re.match(r"\\[a-z]+(?:\s*\{[^}]*\})?", text).end()
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos < len(text) and text[pos] == "[":
        return read_group(text, pos, "[", "]")
    return "", pos


def update_context(context: Context, opts: str, issues: list[Issue], line_no: int):
    for key, value in split_options(opts):
        if key in {"x", "y"}:
            try:
                axis = length_cm(value or "")
                if axis == 0:
                    raise ValueError("zero axis")
                setattr(context, key, axis)
            except ValueError:
                context.geometry_ok = False
                coverage(issues, line_no, f"不支持坐标基 {key}={value}；跳过该上下文的几何比较。")
        elif key not in VISUAL_KEYS:
            context.geometry_ok = False
            coverage(issues, line_no, f"未展开上下文选项/变换 '{key}'；跳过受影响几何。")


def parse_node(text: str, line_no: int, context: Context, scene: Scene):
    try:
        pos, opts, name = len(r"\node"), "", ""
        while True:
            while pos < len(text) and text[pos].isspace():
                pos += 1
            if text[pos:pos + 1] == "[" and not opts:
                opts, pos = read_group(text, pos, "[", "]")
            elif text[pos:pos + 1] == "(" and not name:
                name, pos = read_group(text, pos, "(", ")")
            else:
                break
        at = re.match(r"at\s*", text[pos:])
        if not at:
            raise ValueError("requires literal at (x,y)")
        pos += at.end()
        coord = COORD_PATTERN.match(text, pos)
        if not coord:
            raise ValueError("nonliteral node position")
        pos = coord.end()
        while pos < len(text) and text[pos].isspace():
            pos += 1
        body, _ = read_group(text, pos, "{", "}")
    except (ValueError, IndexError):
        coverage(scene.issues, line_no, "无法解析节点位置/内容；仅支持字面数值 at (x,y) 和花括号内容，未检查该节点。")
        return
    values, dimensions = dict(split_options(opts)), {}
    geometry_ok = context.geometry_ok
    unknown = [key for key in values if key not in VISUAL_KEYS | NODE_KEYS]
    if unknown:
        coverage(scene.issues, line_no, f"节点 '{name}' 的样式/选项未展开: {', '.join(unknown)}；跳过其几何比较。")
        geometry_ok = False
    for key in NODE_KEYS - {"anchor"}:
        if key in values:
            try:
                dimensions[key] = length_cm(values[key] or "")
                if dimensions[key] < 0:
                    raise ValueError("negative dimension")
            except ValueError:
                coverage(scene.issues, line_no, f"节点 '{name}' 的 {key} 不是受支持的非负字面长度；跳过其几何比较。")
                geometry_ok = False
    anchor = values.get("anchor", "center")
    if anchor not in ANCHORS:
        coverage(scene.issues, line_no, f"节点 '{name}' 的 anchor={anchor} 不支持；跳过其几何比较。")
        geometry_ok, anchor = False, "center"
    sep = (10 / 3) * UNITS_CM["pt"]
    inner_x = dimensions.get("inner xsep", dimensions.get("inner sep", sep))
    inner_y = dimensions.get("inner ysep", dimensions.get("inner sep", sep))
    width = dimensions.get("minimum width", 0.)
    if "text width" in dimensions:
        width = max(width, dimensions["text width"] + 2 * inner_x)
    if width <= 0:
        coverage(scene.issues, line_no, f"节点 '{name}' 无可用字面宽度；实际文本宽度需渲染，跳过其几何比较。")
        geometry_ok = False
    line_count = 1 + len(re.findall(r"\\\\|\\newline\b|\\par\b", body))
    baseline = 12 * UNITS_CM["pt"]
    font = values.get("font") or ""
    font_match = re.search(rf"\\fontsize\s*\{{\s*({NUMBER})\s*\}}\s*\{{\s*({NUMBER})\s*\}}", font)
    if font_match:
        baseline = float(font_match[2]) * UNITS_CM["pt"]
    height = dimensions.get("minimum height", 0.)
    estimated = line_count > 1 or "text width" in dimensions or height <= 0
    if line_count > 1 or height <= 0:
        height = max(height, line_count * baseline + 2 * inner_y)
    if estimated:
        scene.issues.append(Issue("WARN", "node-metrics", line_no,
            f"节点 '{name}' 的宽高仅为静态估计/最小值（显式 {line_count} 行，h≈{height:.2f}cm）；"
            "自动折行、数学公式和字体可能增高/增宽，必须查看渲染图。"))
    x, y = float(coord[1]) * context.x, float(coord[2]) * context.y
    ax, ay = ANCHORS[anchor]
    scene.nodes.append(Node(name.strip(), x - ax * width / 2, y - ay * height / 2,
                            width, height, body, line_no, context.group, geometry_ok, estimated))


def parse_scene(content: str) -> Scene:
    clean, scene = strip_comments(content), Scene()
    global_geometry_ok = True
    # Legacy every-* styles and PGF transforms can affect otherwise entirely
    # literal nodes. Their bodies are deliberately not interpreted here.
    global_entries = re.compile(
        r"\\tikzstyle\s*\{\s*every\s+[^}]*\}|\\pgftransform[A-Za-z]*\b"
    )
    for entry in global_entries.finditer(clean):
        line_no = clean.count("\n", 0, entry.start()) + 1
        coverage(scene.issues, line_no,
                 f"未展开全局样式/PGF变换入口 {entry.group()}；跳过几何比较。")
        global_geometry_ok = False
    # A .style definition is inert until used; direct global settings and every-*
    # hooks are not. Do not silently ignore their possible geometry changes.
    for setting in re.finditer(r"\\tikzset\s*\{", clean):
        line_no = clean.count("\n", 0, setting.start()) + 1
        try:
            options, _ = read_group(clean, setting.end() - 1, "{", "}")
            active = [key for key, _ in split_options(options)
                      if not key.endswith("/.style") or key.startswith("every ")]
        except ValueError:
            active = ["unclosed tikzset"]
        if active:
            coverage(scene.issues, line_no, f"未展开全局tikzset设置: {', '.join(active)}；跳过几何比较。")
            global_geometry_ok = False
    context, stack, consumed, picture = Context(geometry_ok=global_geometry_ok), [], 0, 0
    for match in COMMAND_PATTERN.finditer(clean):
        if match.start() < consumed:
            continue
        line_no = clean.count("\n", 0, match.start()) + 1
        command = re.sub(r"\s+", "", match.group())
        if command.startswith(r"\begin"):
            pos = match.end()
            while pos < len(clean) and clean[pos].isspace():
                pos += 1
            opts = ""
            valid = True
            try:
                if clean[pos:pos + 1] == "[":
                    opts, pos = read_group(clean, pos, "[", "]")
            except ValueError:
                coverage(scene.issues, line_no, "上下文选项括号不完整；无法确认坐标变换。")
                valid = False
            stack.append(context)
            if "tikzpicture" in command:
                picture += 1
                context = Context(group=picture, geometry_ok=global_geometry_ok)
            else:
                context = replace(context)
            context.geometry_ok = context.geometry_ok and valid
            update_context(context, opts, scene.issues, line_no)
            consumed = pos
            continue
        if command.startswith(r"\end"):
            context = stack.pop() if stack else Context()
            consumed = match.end()
            continue
        depth, end = 0, match.end()
        while end < len(clean):
            char = clean[end]
            if char == "\\":
                end += 2
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            elif char == ";" and depth == 0:
                break
            end += 1
        if end == len(clean):
            coverage(scene.issues, line_no, "TikZ 命令缺少可解析的分号；后续命令未检查。")
            break
        statement = clean[match.start():end + 1]
        consumed = end + 1
        if command == r"\node":
            parse_node(statement, line_no, context, scene)
        elif command == r"\fill":
            try:
                opts, pos = command_options(statement)
                unsupported = [key for key, _ in split_options(opts) if key not in VISUAL_KEYS]
                if unsupported:
                    coverage(scene.issues, line_no, f"矩形路径样式/变换未展开: {', '.join(unsupported)}；未用作容器。")
                    continue
                rect = re.fullmatch(rf"\s*({COORD_PATTERN.pattern})\s*rectangle\s*({COORD_PATTERN.pattern})\s*;", statement[pos:])
                if rect and context.geometry_ok:
                    x1, y1 = float(rect[2]) * context.x, float(rect[3]) * context.y
                    x2, y2 = float(rect[5]) * context.x, float(rect[6]) * context.y
                    scene.zones.append(Zone(f"rectangle-L{line_no}", min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2), context.group))
                elif not rect:
                    coverage(scene.issues, line_no, "填充路径不是受支持的字面矩形；未用作容器。")
            except ValueError:
                coverage(scene.issues, line_no, "填充命令选项无法解析；未用作容器。")
        else:
            line_end = content.find("\n", end)
            annotation = re.search(r"tikz-validator:\s*([^\n]*)", content[end:line_end if line_end >= 0 else len(content)])
            contracts = set(re.findall(r"orthogonal|monotone-x|monotone-y|edge-gap", annotation[1])) if annotation else set()
            scene.draws.append(Draw(statement, line_no, replace(context), contracts))
    return scene


def parse_nodes(lines: list[str]) -> list[Node]:
    return parse_scene("\n".join(lines)).nodes


def parse_zones(lines: list[str]) -> list[Zone]:
    return parse_scene("\n".join(lines)).zones


def check_label_collision(nodes: list[Node]) -> list[Issue]:
    issues = []
    for i, first in enumerate(nodes):
        for second in nodes[i + 1:]:
            if not (first.name and second.name and first.geometry_ok and second.geometry_ok) or first.group != second.group:
                continue
            dx = abs(first.x - second.x) - (first.width + second.width) / 2
            dy = abs(first.y - second.y) - (first.height + second.height) / 2
            if dx < .15 and dy < .15:
                issues.append(Issue("WARN", "collision", second.line_no,
                    f"节点 '{first.name}' 与 '{second.name}' 的最小/估计矩形接触或过近："
                    f"x间隙={dx:.2f}cm，y间隙={dy:.2f}cm；这是候选，需渲染确认。"))
    return issues


def check_container_overflow(nodes: list[Node], zones: list[Zone]) -> list[Issue]:
    issues = []
    for node in nodes:
        if not (node.name and node.geometry_ok):
            continue
        candidates = [z for z in zones if z.group == node.group and z.x_min <= node.x <= z.x_max and z.y_min <= node.y <= z.y_max]
        if not candidates:
            continue
        zone = min(candidates, key=lambda z: (z.x_max - z.x_min) * (z.y_max - z.y_min))
        if (node.x - node.width / 2 < zone.x_min + .3 or node.x + node.width / 2 > zone.x_max - .3
                or node.y - node.height / 2 < zone.y_min + .3 or node.y + node.height / 2 > zone.y_max - .3):
            issues.append(Issue("WARN", "overflow", node.line_no,
                f"节点 '{node.name}' 的最小/估计矩形距推测容器 '{zone.name}' 边界不足0.3cm；容器归属及溢出需渲染确认。"))
    return issues


def check_routes(draws: list[Draw], nodes: list[Node]) -> list[Issue]:
    issues = []
    node_map = {(n.group, n.name): n for n in nodes if n.name and n.geometry_ok}
    for draw in draws:
        if not draw.contracts:
            continue
        if not draw.context.geometry_ok:
            coverage(issues, draw.line_no, "显式路由约定处于未支持的变换上下文，未检查。")
            continue
        try:
            opts, pos = command_options(draw.text)
        except ValueError:
            coverage(issues, draw.line_no, "显式路由约定的绘图选项无法解析。")
            continue
        unsupported = [key for key, _ in split_options(opts)
                       if key not in VISUAL_KEYS and key not in {"->", "<-", "<->", "-"}]
        if unsupported:
            coverage(issues, draw.line_no, f"路由样式/选项未展开: {', '.join(unsupported)}；显式约定只支持字面绘图选项。")
            continue
        path = draw.text[pos:].strip().removesuffix(";").strip()
        pieces = re.split(r"\s*--\s*", path)
        coords = [COORD_PATTERN.fullmatch(piece) for piece in pieces]
        numeric_contracts = draw.contracts - {"edge-gap"}
        if numeric_contracts:
            if len(coords) < 2 or not all(coords):
                coverage(issues, draw.line_no, "正交/单调约定仅支持完整字面数值 -- 路径；未把命名端点间的途经点当成终点。")
            else:
                points = [Point(float(m[1]) * draw.context.x, float(m[2]) * draw.context.y) for m in coords]
                for a, b in zip(points, points[1:]):
                    if "orthogonal" in numeric_contracts and abs(a.x - b.x) > .05 and abs(a.y - b.y) > .05:
                        issues.append(Issue("WARN", "micro-slope", draw.line_no, "标注为 orthogonal 的路径含双轴均变化的线段；确认约定或调整路由。"))
                for axis in ("x", "y"):
                    if f"monotone-{axis}" not in numeric_contracts:
                        continue
                    total = getattr(points[-1], axis) - getattr(points[0], axis)
                    if any((getattr(b, axis) - getattr(a, axis)) * (1 if total >= 0 else -1) < -.05 for a, b in zip(points, points[1:])):
                        issues.append(Issue("WARN", "direction", draw.line_no, f"路径不满足显式 monotone-{axis} 约定；未据此推断箭头语义错误。"))
        if "edge-gap" in draw.contracts:
            refs = [re.fullmatch(r"\(([^\s().]+)\.(east|west|north|south)\)", p) for p in pieces]
            if len(refs) != 2 or not all(refs):
                coverage(issues, draw.line_no, "edge-gap只检查单条直线及显式相向cardinal锚点；绕行/曲线长度需在PDF中检查。")
                continue
            first, second = [node_map.get((draw.context.group, ref[1])) for ref in refs]
            if first is None or second is None:
                coverage(issues, draw.line_no, "edge-gap端点缺少可用节点几何。")
                continue
            a, b = refs[0][2], refs[1][2]
            if {a, b} == {"east", "west"} and abs(first.y - second.y) < .01:
                gap = (1 if a == "east" else -1) * (second.x - first.x) - (first.width + second.width) / 2
            elif {a, b} == {"north", "south"} and abs(first.x - second.x) < .01:
                gap = (1 if a == "north" else -1) * (second.y - first.y) - (first.height + second.height) / 2
            else:
                coverage(issues, draw.line_no, "edge-gap锚点不共轴或不相向；未用节点中心距离估算路由长度。")
                continue
            if gap < 1.2:
                issues.append(Issue("WARN", "short-arrow", draw.line_no,
                    f"显式edge-gap建议：最小/估计节点边距{gap:.2f}cm < 1.2cm；是否足够以渲染图为准。"))
    return issues


def check_micro_slopes(lines: list[str]) -> list[Issue]:
    scene = parse_scene("\n".join(lines))
    return [i for i in check_routes(scene.draws, scene.nodes) if i.category == "micro-slope"]


def check_direction_reversal(lines: list[str]) -> list[Issue]:
    scene = parse_scene("\n".join(lines))
    return [i for i in check_routes(scene.draws, scene.nodes) if i.category == "direction"]


def check_short_arrows(lines: list[str], nodes: list[Node]) -> list[Issue]:
    scene = parse_scene("\n".join(lines))
    return [i for i in check_routes(scene.draws, nodes) if i.category == "short-arrow"]


def validate_content(content: str) -> list[Issue]:
    scene = parse_scene(content)
    return scene.issues + check_label_collision(scene.nodes) + check_container_overflow(scene.nodes, scene.zones) + check_routes(scene.draws, scene.nodes)


def validate(filepath: str) -> list[Issue]:
    return validate_content(Path(filepath).read_text(encoding="utf-8"))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) != 2:
        print("用法: python tikz-validator.py <file.tex>")
        return 1
    try:
        issues = validate(sys.argv[1])
    except (OSError, UnicodeError) as exc:
        print(f"ERROR: {exc}")
        return 2
    if not issues:
        print("PASS — 支持的静态子集未发现候选问题；不代表TeX布局已验证，仍需PDF检查。")
        return 0
    print(f"TikZ 静态预检: {sys.argv[1]}")
    for issue in issues:
        print(f"{issue.level} [{issue.category}] L{issue.line_no}: {issue.message}")
    print("矩形/边距仅为声明最小值或静态估计；coverage表示未检查，不能据此认定渲染通过。")
    return 2 if any(i.level == "ERROR" for i in issues) else 1


if __name__ == "__main__":
    sys.exit(main())
