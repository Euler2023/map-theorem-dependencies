#!/usr/bin/env python3
r"""
PDF 重叠检测器 — 编译后自动检测渲染结果中的多种几何问题。

用法:
    python3 pdf-overlap-checker.py <file.pdf>            # 人读文本输出
    python3 pdf-overlap-checker.py <file.pdf> --json     # 结构化输出供 sub-agent 消费

几何检测产生待目视复核的候选，不推断字形墨迹是否真的相交：
    text-overlap        两段文字 bbox 相交（IoU > 0.03）            [WARN, candidate]
    text-overflow       文字溢出其容器矩形                          [ERROR/WARN]
    off-center          容器内容偏离中心 / 顶部留白过多              [WARN]
    text-line           文字被水平/垂直线穿过                        [WARN]
    line-crossing       多条 line segment 互相交叉（聚合计数）       [WARN]
  Candidate 2 类（需 sub-agent triage 区分 ignore/fix）：
    line-through-node   line 真穿过 filled rect 内部（PyMuPDF 几何） [ERROR, candidate]
    node-overlap        两个 sibling node rect 几何重叠              [ERROR, candidate]

后两类需 PyMuPDF（pip install pymupdf）。缺失时会打印 ERROR 并退出 — 不静默跳过。

JSON保留全部候选及页码/bbox，附分类及局部复核分组；人读输出每类默认至多8项。
坐标单位为PDF point，原点在页面左上角，bbox=[x0,top,x1,bottom]。
退出码: 0=未发现候选（仍需目视）, 1=有待复核项, 2=有错误或检测不完整。
"""

import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field


@dataclass
class BBox:
    x0: float
    top: float
    x1: float
    bottom: float
    label: str = ""
    path_id: int = -1  # real drawing path when available; -1 for text/fallback

    @property
    def width(self):
        return self.x1 - self.x0

    @property
    def height(self):
        return self.bottom - self.top

    @property
    def cx(self):
        return (self.x0 + self.x1) / 2

    @property
    def cy(self):
        return (self.top + self.bottom) / 2


@dataclass
class Issue:
    level: str  # ERROR, WARN
    category: str
    message: str
    page: int | None = None  # one-based PDF page
    bbox: list[float] | None = None
    related_bboxes: list[dict] = field(default_factory=list)
    candidate: bool = True
    review_status: str = "needs-visual-review"


def issue_location(*boxes: BBox) -> dict:
    """Retain the exact local geometry needed to render/inspect a candidate."""
    return {
        "bbox": [min(b.x0 for b in boxes), min(b.top for b in boxes),
                 max(b.x1 for b in boxes), max(b.bottom for b in boxes)],
        "related_bboxes": [
            {"label": b.label, "bbox": [b.x0, b.top, b.x1, b.bottom],
             "path_id": b.path_id}
            for b in boxes
        ],
    }


class IncompleteCheck(RuntimeError):
    """A required dependency/check failed; never report an automatic pass."""

    def __init__(self, message, partial_issues=None, failed_page=None,
                 uncompleted_pages=None):
        super().__init__(message)
        self.partial_issues = list(partial_issues or [])
        self.failed_page = failed_page
        self.uncompleted_pages = list(uncompleted_pages or [])


def bbox_overlap(a: BBox, b: BBox) -> tuple[float, float]:
    """Return (overlap_x, overlap_y) in points. Positive = overlapping."""
    overlap_x = min(a.x1, b.x1) - max(a.x0, b.x0)
    overlap_y = min(a.bottom, b.bottom) - max(a.top, b.top)
    return overlap_x, overlap_y


def bbox_iou(a: BBox, b: BBox) -> float:
    """Intersection over Union of two bounding boxes."""
    ox, oy = bbox_overlap(a, b)
    if ox <= 0 or oy <= 0:
        return 0.0
    intersection = ox * oy
    area_a = a.width * a.height
    area_b = b.width * b.height
    union = area_a + area_b - intersection
    if union <= 0:
        return 0.0
    return intersection / union


def gap_between(a: BBox, b: BBox) -> float:
    """Minimum gap between two bboxes (negative = overlapping)."""
    ox, oy = bbox_overlap(a, b)
    if ox > 0 and oy > 0:
        return -min(ox, oy)  # overlapping
    # Not overlapping - find closest gap
    gap_x = max(a.x0, b.x0) - min(a.x1, b.x1)
    gap_y = max(a.top, b.top) - min(a.bottom, b.bottom)
    if gap_x > 0 and gap_y > 0:
        return min(gap_x, gap_y)
    return max(gap_x, gap_y) if gap_x > 0 or gap_y > 0 else -min(abs(gap_x), abs(gap_y))


def is_same_text(a: BBox, b: BBox) -> bool:
    """Check if two words are essentially the same element (overlaid intentionally)."""
    return (a.label == b.label and abs(a.x0 - b.x0) < 1.0 and abs(a.top - b.top) < 1.0 and
            abs(a.x1 - b.x1) < 1.0 and abs(a.bottom - b.bottom) < 1.0)


def is_inside(inner: BBox, outer: BBox, margin: float = 0) -> bool:
    """Check if inner bbox is fully inside outer bbox with optional margin."""
    return (inner.x0 >= outer.x0 - margin and
            inner.x1 <= outer.x1 + margin and
            inner.top >= outer.top - margin and
            inner.bottom <= outer.bottom + margin)


def find_container(word: BBox, rects: list[BBox]) -> BBox | None:
    """Find the smallest rectangle that contains the word's center."""
    best = None
    best_area = float('inf')

    for rect in rects:
        # Skip very small rects (decorations) and very large rects (page-level backgrounds)
        if rect.width < 10 or rect.height < 8:
            continue
        if rect.width > 500 and rect.height > 500:
            continue

        # Check if word center is inside rect
        if (rect.x0 <= word.cx <= rect.x1 and
                rect.top <= word.cy <= rect.bottom):
            area = rect.width * rect.height
            if area < best_area:
                best = rect
                best_area = area

    return best


def check_word_overlaps(words: list[BBox]) -> list[Issue]:
    """Check nearby word pairs for overlapping bounding boxes."""
    issues = []
    MIN_GAP = 1.5  # minimum gap in points
    PROXIMITY = 50.0  # compare words within 50pt (increased from 30)

    for i in range(len(words)):
        for j in range(i + 1, len(words)):
            a, b = words[i], words[j]

            # Quick proximity filter — skip pairs that are far apart
            if abs(a.cx - b.cx) > PROXIMITY + a.width / 2 + b.width / 2:
                continue
            if abs(a.cy - b.cy) > PROXIMITY + a.height / 2 + b.height / 2:
                continue

            # Skip if same text at same position (intentional)
            if is_same_text(a, b):
                continue

            ox, oy = bbox_overlap(a, b)
            if ox > 0 and oy > 0:
                iou = bbox_iou(a, b)
                if iou > 0.03:
                    # Word boxes combine baselines and scripts; overlap alone
                    # cannot prove ink collision (fractions, limits, kerning).
                    # Keep EVERY candidate, including tiny glyphs. Do not use
                    # a mathematical-symbol whitelist to suppress real defects.
                    issues.append(Issue(
                        level="WARN",
                        category="text-overlap",
                        message=f"文字框交叠候选: \"{a.label}\" 和 \"{b.label}\" "
                                f"IoU={iou:.3f} (交叠 {ox:.1f}×{oy:.1f}pt；需看字形)",
                        **issue_location(a, b),
                    ))
            else:
                # Check tight spacing only for truly adjacent elements
                g = gap_between(a, b)
                if 0 < g < MIN_GAP:
                    # Must be in same row (y overlap) or same column (x overlap)
                    y_overlap = min(a.bottom, b.bottom) - max(a.top, b.top)
                    x_overlap = min(a.x1, b.x1) - max(a.x0, b.x0)
                    if y_overlap > min(a.height, b.height) * 0.5 or \
                       x_overlap > min(a.width, b.width) * 0.5:
                        issues.append(Issue(
                            level="WARN",
                            category="text-tight",
                            message=f"文字间距过小: \"{a.label}\" 和 \"{b.label}\" "
                                    f"间距仅 {g:.1f}pt",
                            **issue_location(a, b),
                        ))

    return issues


def check_text_overflow(words: list[BBox], rects: list[BBox]) -> list[Issue]:
    """Check if any text overflows its container rectangle."""
    issues = []
    TOLERANCE = 2.0  # tolerance in points

    for word in words:
        container = find_container(word, rects)
        if container is None:
            continue

        # Check each side
        overflows = []
        if word.x0 < container.x0 - TOLERANCE:
            overflows.append(f"左溢出 {container.x0 - word.x0:.1f}pt")
        if word.x1 > container.x1 + TOLERANCE:
            overflows.append(f"右溢出 {word.x1 - container.x1:.1f}pt")
        if word.top < container.top - TOLERANCE:
            overflows.append(f"上溢出 {container.top - word.top:.1f}pt")
        if word.bottom > container.bottom + TOLERANCE:
            overflows.append(f"下溢出 {word.bottom - container.bottom:.1f}pt")

        if overflows:
            max_overflow = max(
                container.x0 - word.x0 if word.x0 < container.x0 else 0,
                word.x1 - container.x1 if word.x1 > container.x1 else 0,
                container.top - word.top if word.top < container.top else 0,
                word.bottom - container.bottom if word.bottom > container.bottom else 0,
            )
            level = "ERROR" if max_overflow > 5.0 else "WARN"
            issues.append(Issue(
                level=level,
                category="text-overflow",
                message=f"文字溢出容器: \"{word.label}\" {', '.join(overflows)}",
                **issue_location(word, container),
            ))

    return issues


def check_content_balance(words: list[BBox], rects: list[BBox]) -> list[Issue]:
    """Check if content inside large containers is reasonably centered."""
    issues = []
    MIN_CONTAINER = 80.0  # only check containers > 80pt (about 2.8cm)

    for rect in rects:
        if rect.width < MIN_CONTAINER or rect.height < MIN_CONTAINER:
            continue
        # Skip very large rects (page-level)
        if rect.width > 500 and rect.height > 500:
            continue

        # Find all words inside this container
        inside_words = [w for w in words
                        if rect.x0 <= w.cx <= rect.x1 and rect.top <= w.cy <= rect.bottom]
        if len(inside_words) < 2:
            continue

        # Calculate content bounding box
        content_x0 = min(w.x0 for w in inside_words)
        content_x1 = max(w.x1 for w in inside_words)
        content_top = min(w.top for w in inside_words)
        content_bottom = max(w.bottom for w in inside_words)

        # Check horizontal centering
        left_margin = content_x0 - rect.x0
        right_margin = rect.x1 - content_x1
        if rect.width > 100 and left_margin > 0 and right_margin > 0:
            margin_ratio = max(left_margin, right_margin) / max(min(left_margin, right_margin), 1)
            if margin_ratio > 4.0:
                issues.append(Issue(
                    level="WARN",
                    category="off-center",
                    message=f"内容偏移: 容器({rect.width:.0f}×{rect.height:.0f}pt) "
                            f"左margin={left_margin:.0f}pt 右margin={right_margin:.0f}pt "
                            f"(比值 {margin_ratio:.1f}:1)",
                    **issue_location(rect),
                ))

        # Check top-heavy (title bar takes too much space)
        top_margin = content_top - rect.top
        bottom_margin = rect.bottom - content_bottom
        if rect.height > 100 and top_margin > 0 and bottom_margin > 0:
            if top_margin > rect.height * 0.4:
                issues.append(Issue(
                    level="WARN",
                    category="top-heavy",
                    message=f"上方留白过多: 容器高 {rect.height:.0f}pt, "
                            f"上方留白 {top_margin:.0f}pt ({top_margin/rect.height*100:.0f}%)",
                    **issue_location(rect),
                ))

    return issues


def check_text_line_overlap(words: list[BBox], lines: list[BBox]) -> list[Issue]:
    """Check if text overlaps with lines (arrows, zone borders, connections)."""
    issues = []
    BUFFER = 2.0  # minimum distance from text to line in points

    for word in words:
        if word.width < 8:  # skip tiny text
            continue
        for line in lines:
            # Expand line bbox by buffer
            lx0 = min(line.x0, line.x1) - BUFFER
            ly0 = min(line.top, line.bottom) - BUFFER
            lx1 = max(line.x0, line.x1) + BUFFER
            ly1 = max(line.top, line.bottom) + BUFFER

            # Check if word bbox intersects expanded line bbox
            if (word.x0 < lx1 and word.x1 > lx0 and
                    word.top < ly1 and word.bottom > ly0):
                # Calculate how much the word center is inside the line region
                # Only flag if the line actually crosses through the text area
                # (not just touching at edges)
                line_is_horizontal = abs(line.bottom - line.top) < 3
                line_is_vertical = abs(line.x1 - line.x0) < 3

                if line_is_horizontal:
                    line_y = (line.top + line.bottom) / 2
                    if word.top + 2 < line_y < word.bottom - 2:
                        issues.append(Issue(
                            level="WARN",
                            category="text-line",
                            message=f"线穿过文字: \"{word.label}\" "
                                    f"(水平线 y={line_y:.0f} 穿过文字区域 "
                                    f"y={word.top:.0f}-{word.bottom:.0f})",
                            **issue_location(word, line),
                        ))
                elif line_is_vertical:
                    line_x = (line.x0 + line.x1) / 2
                    if word.x0 + 2 < line_x < word.x1 - 2:
                        issues.append(Issue(
                            level="WARN",
                            category="text-line",
                            message=f"线穿过文字: \"{word.label}\" "
                                    f"(垂直线 x={line_x:.0f} 穿过文字区域 "
                                    f"x={word.x0:.0f}-{word.x1:.0f})",
                            **issue_location(word, line),
                        ))
    return issues


def segments_intersect(ax0, ay0, ax1, ay1, bx0, by0, bx1, by1) -> bool:
    """Check if two line segments intersect (excluding shared endpoints)."""
    def cross(ox, oy, ax, ay, bx, by):
        return (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)

    d1 = cross(bx0, by0, bx1, by1, ax0, ay0)
    d2 = cross(bx0, by0, bx1, by1, ax1, ay1)
    d3 = cross(ax0, ay0, ax1, ay1, bx0, by0)
    d4 = cross(ax0, ay0, ax1, ay1, bx1, by1)

    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True
    return False


def check_line_crossings(lines: list[BBox]) -> list[Issue]:
    """Detect lines crossing each other — messy connection areas."""
    issues = []
    MIN_LENGTH = 15.0  # ignore tiny lines (box borders, ticks)

    # Filter to meaningful lines
    real_lines = []
    for ln in lines:
        length = ((ln.x1 - ln.x0)**2 + (ln.bottom - ln.top)**2)**0.5
        if length >= MIN_LENGTH:
            real_lines.append(ln)

    for i in range(len(real_lines)):
        for j in range(i + 1, len(real_lines)):
            a, b = real_lines[i], real_lines[j]
            if segments_intersect(a.x0, a.top, a.x1, a.bottom,
                                  b.x0, b.top, b.x1, b.bottom):
                issues.append(Issue(
                    level="WARN",
                    category="line-crossing",
                    message="两条线段相交候选；请目视判断交点或汇合是否有意。",
                    **issue_location(a, b),
                ))

    return issues


@dataclass
class Segment:
    """A line segment with real endpoints (not just a bbox)."""
    x0: float
    y0: float
    x1: float
    y1: float
    dashed: bool = False
    color: tuple = (0, 0, 0)
    path_id: int = -1  # which PyMuPDF drawing path this segment belongs to

    def length(self) -> float:
        return ((self.x1 - self.x0) ** 2 + (self.y1 - self.y0) ** 2) ** 0.5


def liang_barsky_clip(seg: Segment, rect: BBox) -> tuple[float, float] | None:
    """Liang-Barsky line-rect clipping. Returns (t_enter, t_exit) in [0,1] or None.

    Coordinate convention: PyMuPDF uses top-left origin, y grows downward.
    rect.top < rect.bottom (since top=y_min, bottom=y_max in our BBox).
    """
    dx = seg.x1 - seg.x0
    dy = seg.y1 - seg.y0
    p = [-dx, dx, -dy, dy]
    q = [seg.x0 - rect.x0, rect.x1 - seg.x0, seg.y0 - rect.top, rect.bottom - seg.y0]

    t_enter, t_exit = 0.0, 1.0
    for i in range(4):
        if p[i] == 0:
            if q[i] < 0:
                return None  # parallel and outside
        else:
            t = q[i] / p[i]
            if p[i] < 0:
                t_enter = max(t_enter, t)
            else:
                t_exit = min(t_exit, t)
    if t_enter > t_exit:
        return None
    return t_enter, t_exit


def point_on_rect_boundary(x: float, y: float, rect: BBox, tol: float = 1.5) -> bool:
    """Check if (x, y) sits on rect's edge within tolerance."""
    on_h = (abs(y - rect.top) <= tol or abs(y - rect.bottom) <= tol) and \
           (rect.x0 - tol <= x <= rect.x1 + tol)
    on_v = (abs(x - rect.x0) <= tol or abs(x - rect.x1) <= tol) and \
           (rect.top - tol <= y <= rect.bottom + tol)
    return on_h or on_v


def point_in_rect(x: float, y: float, rect: BBox, margin: float = -2.0) -> bool:
    """Check if (x, y) is strictly inside rect (with shrink margin for tolerance)."""
    return (rect.x0 - margin <= x <= rect.x1 + margin and
            rect.top - margin <= y <= rect.bottom + margin)


def candidate_node_indices(rects: list[BBox], min_dim: float = 6) -> list[int]:
    """Keep wide/shallow nodes; omit decoration and clear nested containers.

    An absolute 140pt width cap excluded ordinary nodes on a large canvas.
    A larger rectangle is treated as a container only when it fully encloses
    a distinct, plausibly node-sized box occupying at least 5% of its area.
    This is still a geometric heuristic, reported in coverage, not a semantic
    proof that each retained shape is a theorem node.
    """
    candidates = []
    for i, rect in enumerate(rects):
        if min(rect.width, rect.height) < min_dim:
            continue
        area = rect.width * rect.height
        has_child = any(
            j != i and child.width >= 30 and child.height >= 15
            and .05 * area <= child.width * child.height <= .85 * area
            and is_inside(child, rect, margin=-1)
            for j, child in enumerate(rects)
        )
        if not has_child:
            candidates.append(i)
    return candidates


def check_line_through_nodes(
    segments: list[Segment],
    rects: list[BBox],
    rect_path_ids: list[int] | None = None,
) -> list[Issue]:
    """Detect lines whose interior passes through a filled rectangle node.

    Logic:
      For each segment AB and each candidate node rect R:
        - Skip if segment came from the same PyMuPDF path that produced R
          (a node's outline segments trivially "cross" its own bbox).
        - Clip AB against R via Liang-Barsky.
        - If both endpoints of AB are outside R and the clipped interval
          [t_in, t_out] has t_in > 0.05 and t_out < 0.95 (i.e. line crosses
          the interior, not just touching at endpoints) → flag.

    Filters:
      - Skip clear nested containers; retain wide or shallow nodes.
      - Skip tiny rects (decorations): width < 6 OR height < 6.
      - Skip very short segments: length < 15pt (likely box borders themselves).
      - Multiple hits on one rect remain candidates; never erase a cluster.
    """
    if rect_path_ids is None:
        rect_path_ids = [-1] * len(rects)
    raw_hits = []     # collect first, cluster-filter second
    flagged = set()

    candidate_rects = [
        (ri, rects[ri]) for ri in candidate_node_indices(rects)
    ]

    for seg in segments:
        if seg.length() < 15:
            continue
        for ri, rect in candidate_rects:
            both_inside = False  # explicit init so the bypass check below is robust
            # Skip "node's own outline segment crosses its own bbox" false positives.
            if seg.path_id >= 0 and rect_path_ids[ri] == seg.path_id:
                continue
            # Endpoint-on-boundary handling: an arrow that terminates at a
            # node's edge is *usually* a clean incoming connection — but NOT
            # if its stem also travels through the node's interior on the way
            # to that edge.  fig97 (Batch 10) hit this: an L-bend ((A.south) |-
            # (B.west)) where A's x sat inside B's x range routes the
            # horizontal leg *through* B's interior before landing on B.west.
            # So we only auto-skip when the endpoint approaches from outside.
            ep0_on_boundary = point_on_rect_boundary(seg.x0, seg.y0, rect)
            ep1_on_boundary = point_on_rect_boundary(seg.x1, seg.y1, rect)
            if ep0_on_boundary and ep1_on_boundary:
                # Both endpoints on boundary — could be either:
                #  (a) the rect's own stroke edge (top/bottom/left/right line),
                #      drawn by a separate "stroke" path even when fill came
                #      from another path → SKIP these.
                #  (b) a spanning chord through the node interior — true bug.
                # Distinguish: check if seg lies along one of the 4 edges.
                tol = 2.0
                on_top    = abs(seg.y0 - rect.top)    <= tol and abs(seg.y1 - rect.top)    <= tol
                on_bot    = abs(seg.y0 - rect.bottom) <= tol and abs(seg.y1 - rect.bottom) <= tol
                on_left   = abs(seg.x0 - rect.x0)     <= tol and abs(seg.x1 - rect.x0)     <= tol
                on_right  = abs(seg.x0 - rect.x1)     <= tol and abs(seg.x1 - rect.x1)     <= tol
                if on_top or on_bot or on_left or on_right:
                    continue  # rect's own edge
                # Not on an edge → spanning chord through interior → flag.
            elif ep0_on_boundary or ep1_on_boundary:
                # Check whether the *other* endpoint is outside the rect.
                # If yes AND the line's interior dwell-fraction is large,
                # the line is routing through the body to reach the edge.
                other_x = seg.x1 if ep0_on_boundary else seg.x0
                other_y = seg.y1 if ep0_on_boundary else seg.y0
                if point_in_rect(other_x, other_y, rect, margin=-3):
                    # Other endpoint inside → not a "pass through" case;
                    # it's a connection between an external point and an
                    # internal anchor.  Skip.
                    continue
                # Other endpoint outside: compute how much of the segment
                # actually lies *inside* the rect.  If > 30% of length, this
                # is the |- pierce bug; flag it.  Otherwise it's a normal
                # connection just touching the boundary at endpoint.
                clip_chk = liang_barsky_clip(seg, rect)
                if clip_chk is None:
                    continue
                inside_frac = clip_chk[1] - clip_chk[0]
                if inside_frac < 0.3:
                    continue
                # Fall through to the rest of the checks (which will re-clip
                # and emit the issue).
            else:
                ep0_inside = point_in_rect(seg.x0, seg.y0, rect, margin=-3)
                ep1_inside = point_in_rect(seg.x1, seg.y1, rect, margin=-3)
                if ep0_inside and ep1_inside:
                    # BOTH endpoints inside the rect — this is the `|-` /
                    # `-|` pierce pattern (fig97 Batch 10):
                    #   \draw[arrow] (A.south) |- (B.west)
                    # generates a short horizontal segment fully *inside* B,
                    # running from (A.x, B.cy) to (B.cx_inner, B.cy).
                    # Flag it as a line-through-node bug.  Spine filter above
                    # already excluded "long axis lines on rect's centerline"
                    # legitimate cases (lifelines).
                    both_inside = True  # used below to bypass t_in/t_out check
                else:
                    both_inside = False
                    if ep0_inside or ep1_inside:
                        # One inside, one outside — line crosses the boundary
                        # somewhere in the middle.  Skip: this is the normal
                        # "anchor=center" / "label points inward" case.
                        continue
            # A vertical line on the rect's vertical centerline
            # (±3pt) and much longer than the rect's height is a designed
            # "spine" — e.g. a sequence-diagram lifeline passing through its
            # actor header box, or a swimlane axis crossing a phase label.
            # Same for horizontal lines on the rect's horizontal centerline.
            # Keep it as WARN candidate: a geometric axis guess cannot establish
            # that the crossing was intentional.
            is_vertical = abs(seg.x1 - seg.x0) < 1.0
            is_horizontal = abs(seg.y1 - seg.y0) < 1.0
            rect_cx = (rect.x0 + rect.x1) / 2
            rect_cy = (rect.top + rect.bottom) / 2
            possible_spine = (
                (is_vertical and abs(seg.x0 - rect_cx) <= 3
                 and seg.length() > rect.height * 3)
                or (is_horizontal and abs(seg.y0 - rect_cy) <= 3
                    and seg.length() > rect.width * 3)
            )
            clip = liang_barsky_clip(seg, rect)
            if clip is None:
                continue
            t_in, t_out = clip
            # Require crossing to be "through" — not just glancing edge.
            # Two exceptions:
            #   (a) endpoint-on-boundary case: t_in (or t_out) is legitimately
            #       0 (or 1).  Boundary filter above already gated this.
            #   (b) both-endpoints-inside case: t_in=0 and t_out=1 always —
            #       the segment lives entirely inside the rect.  This is the
            #       fig97 |- pierce bug; allow it through.
            ep_on_boundary = (ep0_on_boundary or ep1_on_boundary)
            bypass_through_check = ep_on_boundary or both_inside
            if not bypass_through_check:
                if t_in <= 0.05 or t_out >= 0.95:
                    continue
            crossing_length = (t_out - t_in) * seg.length()
            if crossing_length < 3:  # very short crossing — likely numerical noise
                continue
            key = (round(seg.x0), round(seg.y0), round(seg.x1), round(seg.y1), ri)
            if key in flagged:
                continue
            flagged.add(key)
            dash_tag = "dashed " if seg.dashed else ""
            raw_hits.append((ri, Issue(
                level="WARN" if possible_spine else "ERROR",
                category="line-through-node",
                message=f"{dash_tag}线穿过节点: 从({seg.x0:.0f},{seg.y0:.0f})→"
                        f"({seg.x1:.0f},{seg.y1:.0f}) 穿过 "
                        f"rect[{rect.x0:.0f},{rect.top:.0f},{rect.x1:.0f},{rect.bottom:.0f}] "
                        f"内部 (crossing {crossing_length:.0f}pt)"
                        + ("；可能是有意的中心轴，仍需复核" if possible_spine else ""),
                **issue_location(rect, BBox(min(seg.x0, seg.x1), min(seg.y0, seg.y1),
                                          max(seg.x0, seg.x1), max(seg.y0, seg.y1), "segment",
                                          path_id=seg.path_id)),
            )))

    return [iss for _ri, iss in raw_hits]


def check_node_overlap(
    rects: list[BBox],
    rect_path_ids: list[int] | None = None,
) -> list[Issue]:
    """Detect pairs of node-sized rects that geometrically overlap (sibling
    overlap, not parent-child containment).

    Filters:
      - Decorations and clear nested containers are excluded; no width cap.
      - Skip pairs from the same drawing path (same node).
      - Skip pairs where one fully contains the other (zone-in-zone, panel
        holding a child node).
      - Require IoU ≥ 0.05 — micro overlaps from bbox synthesis are noise.
    """
    if rect_path_ids is None:
        rect_path_ids = [-1] * len(rects)
    issues = []
    # Tighter min dim than line-through-node check: glyph fills are 4-8pt and
    # would generate spurious overlaps. A real node is at least ~10pt on its
    # short side. Y-fork junction dots (~4-5pt) are intentionally excluded —
    # overlap detection at that scale is noise.
    MIN_IOU = 0.05

    nodes = [
        (i, rects[i], rect_path_ids[i])
        for i in candidate_node_indices(rects, min_dim=10)
    ]

    seen_pairs = set()
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            _ri, a, pi = nodes[i]
            _rj, b, pj = nodes[j]
            if pi >= 0 and pi == pj:
                continue  # same drawing path
            # Skip identical rects (two paths drew the same outline + fill)
            if abs(a.x0 - b.x0) < 1 and abs(a.x1 - b.x1) < 1 \
                    and abs(a.top - b.top) < 1 and abs(a.bottom - b.bottom) < 1:
                continue
            # Possible drop-shadow pattern: TikZ `drop shadow` draws the same box
            # twice — a grey shadow offset by ~2-3pt + the main fill rect.
            # Two rects of nearly identical W/H whose centers differ by ≤5pt
            # in both axes may be a shadow; retain rather than silently skip it.
            possible_shadow = False
            if abs(a.width - b.width) < 3 and abs(a.height - b.height) < 3:
                a_cx, a_cy = (a.x0 + a.x1) / 2, (a.top + a.bottom) / 2
                b_cx, b_cy = (b.x0 + b.x1) / 2, (b.top + b.bottom) / 2
                if abs(a_cx - b_cx) <= 5 and abs(a_cy - b_cy) <= 5 \
                        and (abs(a_cx - b_cx) > 0.5 or abs(a_cy - b_cy) > 0.5):
                    possible_shadow = True  # retain for visual triage
            # Parent-child? one fully inside the other → OK
            if is_inside(a, b, margin=2) or is_inside(b, a, margin=2):
                continue
            iou = bbox_iou(a, b)
            if iou < MIN_IOU:
                continue
            key = (round(a.x0), round(a.top), round(a.x1), round(a.bottom),
                   round(b.x0), round(b.top), round(b.x1), round(b.bottom))
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            ox, oy = bbox_overlap(a, b)
            issues.append(Issue(
                level="WARN" if possible_shadow else "ERROR",
                category="node-overlap",
                message=f"节点重叠: rect[{a.x0:.0f},{a.top:.0f},{a.x1:.0f},{a.bottom:.0f}] "
                        f"vs rect[{b.x0:.0f},{b.top:.0f},{b.x1:.0f},{b.bottom:.0f}] "
                        f"IoU={iou:.3f} (重叠 {ox:.1f}×{oy:.1f}pt)"
                        + ("；可能是投影阴影，仍需复核" if possible_shadow else ""),
                **issue_location(a, b),
            ))
    return issues


def extract_pymupdf_geometry(filepath: str, page_index: int = 0):
    """Use PyMuPDF to extract real line endpoints + curves + filled rects.

    Returns (segments, curves_as_bboxes, rects_filled, rects_stroke,
              rects_filled_path_id).  Each Segment carries its own
              `path_id` so callers can skip self-comparisons (a node's
              outline segments vs the same node's bbox rect).
    Raises IncompleteCheck if PyMuPDF is unavailable; never silently skip.
    """
    try:
        import fitz
    except ImportError:
        raise IncompleteCheck(
            "缺少 pymupdf (fitz)；line-through-node / node-overlap 未运行。"
        ) from None

    pdf = fitz.open(filepath)
    if pdf.page_count == 0:
        return [], [], [], [], []
    page = pdf[page_index]
    drawings = page.get_drawings()

    segments: list[Segment] = []
    curve_bboxes: list[BBox] = []
    rects_filled: list[BBox] = []
    rects_stroke: list[BBox] = []

    # Track which path id each filled rect came from, so check_line_through_nodes
    # can skip "a path's own segments cross its own bbox" false positives.
    rects_filled_path_id: list[int] = []  # parallel to rects_filled

    for pid, d in enumerate(drawings):
        dashes = d.get("dashes")
        # PyMuPDF represents a SOLID stroke as the nonempty string "[] 0".
        is_dashed = (bool(dashes.split("]", 1)[0].lstrip(" ["))
                     if isinstance(dashes, str) else bool(dashes))
        stroke = d.get("color")
        fill = d.get("fill")
        # Track this path's overall bbox so we can register a *filled* path
        # (TikZ-style filled box drawn as 4 line segments) as a node rect.
        path_xs: list[float] = []
        path_ys: list[float] = []

        for it in d.get("items", []):
            op = it[0]
            if op == "l":
                p1, p2 = it[1], it[2]
                segments.append(Segment(
                    x0=p1.x, y0=p1.y, x1=p2.x, y1=p2.y,
                    dashed=is_dashed, color=stroke or (0, 0, 0), path_id=pid
                ))
                path_xs.extend([p1.x, p2.x])
                path_ys.extend([p1.y, p2.y])
            elif op == "c":
                # Bezier control points: p0, p1, p2, p3
                pts = [it[1], it[2], it[3], it[4]] if len(it) > 4 else list(it[1:])
                if pts:
                    xs = [p.x for p in pts]
                    ys = [p.y for p in pts]
                    curve_bboxes.append(BBox(
                        x0=min(xs), top=min(ys),
                        x1=max(xs), bottom=max(ys),
                        label="bezier"
                    ))
                    path_xs.extend(xs)
                    path_ys.extend(ys)
                    # Also approximate the curve with chord segments for through-node test
                    if len(pts) >= 2:
                        for i in range(len(pts) - 1):
                            segments.append(Segment(
                                x0=pts[i].x, y0=pts[i].y,
                                x1=pts[i + 1].x, y1=pts[i + 1].y,
                                dashed=is_dashed, color=stroke or (0, 0, 0),
                                path_id=pid
                            ))
            elif op == "re":
                r = it[1]
                bb = BBox(x0=r.x0, top=r.y0, x1=r.x1, bottom=r.y1,
                          label="rect", path_id=pid)
                if fill is not None:
                    rects_filled.append(bb)
                    rects_filled_path_id.append(pid)
                else:
                    rects_stroke.append(bb)
                path_xs.extend([r.x0, r.x1])
                path_ys.extend([r.y0, r.y1])

        # If the path is filled (fill color set) AND has geometric extent that
        # *isn't* already captured by a `re` operator above, register it as a
        # synthesized filled rect (covers the common TikZ case of a node drawn
        # as 4 lines + fill).
        if fill is not None and path_xs and path_ys:
            x0, x1 = min(path_xs), max(path_xs)
            y0, y1 = min(path_ys), max(path_ys)
            w, h = x1 - x0, y1 - y0
            # Skip degenerate (line-shaped) and page-sized fills.
            if w >= 4 and h >= 4 and not (w > 500 and h > 500):
                rects_filled.append(BBox(
                    x0=x0, top=y0, x1=x1, bottom=y1, label="filled-path", path_id=pid
                ))
                rects_filled_path_id.append(pid)

    pdf.close()
    return segments, curve_bboxes, rects_filled, rects_stroke, rects_filled_path_id


def merge_node_rectangles(filled, filled_path_ids, stroke, fallback):
    """Union every rectangle source; a small fill must not hide stroke nodes.

    Prefer real path IDs and deduplicate only geometrically coincident boxes.
    Do not use a filled-versus-stroked either/or fallback.
    """
    merged, path_ids = [], []
    candidates = (list(zip(filled, filled_path_ids))
                  + [(r, r.path_id) for r in stroke]
                  + [(r, -1) for r in fallback])
    for rect, path_id in candidates:
        duplicate = next((i for i, previous in enumerate(merged)
                          if max(abs(rect.x0-previous.x0), abs(rect.top-previous.top),
                                 abs(rect.x1-previous.x1), abs(rect.bottom-previous.bottom)) < .5), None)
        if duplicate is None:
            merged.append(rect)
            path_ids.append(path_id)
        elif path_ids[duplicate] < 0 <= path_id:
            merged[duplicate] = rect
            path_ids[duplicate] = path_id
    return merged, path_ids


def _validate_pdf_page(filepath: str, page_index: int = 0,
                       coverage: list[dict] | None = None) -> list[Issue]:
    """Main validation: extract PDF elements and check for overlaps."""
    try:
        import pdfplumber
    except ImportError:
        raise IncompleteCheck("缺少 pdfplumber；文字与几何检查未完成。") from None

    pdf = pdfplumber.open(filepath)
    if not pdf.pages:
        pdf.close()
        raise IncompleteCheck("PDF 没有页面。")

    page = pdf.pages[page_index]

    # Extract words with bounding boxes
    raw_words = page.extract_words(
        keep_blank_chars=False,
        x_tolerance=3,
        y_tolerance=3,
    )

    words = []
    for w in raw_words:
        text = w.get("text", "").strip()
        if not text or len(text) < 1:
            continue
        words.append(BBox(
            x0=float(w["x0"]),
            top=float(w["top"]),
            x1=float(w["x1"]),
            bottom=float(w["bottom"]),
            label=text[:25],  # truncate for display
        ))

    # Extract rectangles (container boxes)
    raw_rects = page.rects or []
    rects = []
    for r in raw_rects:
        rects.append(BBox(
            x0=float(r["x0"]),
            top=float(r["top"]),
            x1=float(r["x1"]),
            bottom=float(r["bottom"]),
            label="rect",
        ))

    # Extract lines (arrows, connections, zone borders)
    raw_lines = page.lines or []
    pdf_lines = []
    for ln in raw_lines:
        pdf_lines.append(BBox(
            x0=float(ln["x0"]),
            top=float(ln["top"]),
            x1=float(ln["x1"]),
            bottom=float(ln["bottom"]),
            label="line",
        ))

    # Also extract curves (dashed lines, arcs, bezier paths)
    raw_curves = page.curves or []
    for crv in raw_curves:
        # Use the bounding box of the curve's points
        pts = crv.get("pts", [])
        if not pts:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if xs and ys:
            pdf_lines.append(BBox(
                x0=min(xs), top=min(ys),
                x1=max(xs), bottom=max(ys),
                label="curve",
            ))

    all_issues: list[Issue] = []

    # 1. Text-text overlap
    all_issues.extend(check_word_overlaps(words))

    # 2. Text overflow from container
    if rects:
        all_issues.extend(check_text_overflow(words, rects))

    # 3. Content centering and balance inside containers
    if rects:
        all_issues.extend(check_content_balance(words, rects))

    # 4. Text-line overlap (text crossed by arrows or zone borders)
    if pdf_lines:
        all_issues.extend(check_text_line_overlap(words, pdf_lines))

    # 5. Line-line crossings (messy connection areas)
    if pdf_lines:
        all_issues.extend(check_line_crossings(pdf_lines))

    pdf.close()

    # 6. Line-through-node: merge filled AND stroke-only nodes, with fallback
    # rectangles supplementing rather than replacing either geometry source.
    segments, _curves, rects_filled, rects_stroke, rect_pids = extract_pymupdf_geometry(filepath, page_index)
    if segments is not None:
        node_rects, node_rect_pids = merge_node_rectangles(
            rects_filled, rect_pids, rects_stroke, rects)
        if coverage is not None:
            selected = set(candidate_node_indices(node_rects))
            coverage.append({
                "page": page_index + 1,
                "filled_rect_count": len(rects_filled),
                "stroke_rect_count": len(rects_stroke),
                "merged_rect_count": len(node_rects),
                "node_candidate_count": len(selected),
                "excluded_rectangles": [
                    {"bbox": [r.x0, r.top, r.x1, r.bottom],
                     "reason": "decoration" if min(r.width, r.height) < 6 else "nested-container"}
                    for ri, r in enumerate(node_rects) if ri not in selected
                ],
            })
        if node_rects:
            all_issues.extend(check_line_through_nodes(segments, node_rects, node_rect_pids))
            # 7. Node-vs-node geometric overlap (sibling intersection).
            all_issues.extend(check_node_overlap(node_rects, node_rect_pids))

    for issue in all_issues:
        issue.page = page_index + 1
    return all_issues


def validate_pdf(filepath: str, coverage: list[dict] | None = None) -> list[Issue]:
    """Run required checks on every page, or raise an incomplete-check error."""
    try:
        import fitz
    except ImportError:
        raise IncompleteCheck("缺少 pymupdf (fitz)；几何检测未运行。") from None
    with fitz.open(filepath) as pdf:
        page_count = pdf.page_count
    if not page_count:
        raise IncompleteCheck("PDF 没有页面。")
    issues = []
    for page_index in range(page_count):
        try:
            issues.extend(_validate_pdf_page(filepath, page_index, coverage))
        except (IncompleteCheck, ImportError, OSError, ValueError, RuntimeError) as exc:
            raise IncompleteCheck(
                f"第{page_index+1}页检查中断；该页及后续页未完成: {exc}",
                partial_issues=issues, failed_page=page_index+1,
                uncompleted_pages=list(range(page_index+1, page_count+1)),
            ) from exc
    return issues


def build_report(filepath: str, issues: list[Issue], coverage: list[dict],
                 complete: bool = True) -> dict:
    """Keep full findings; summarize nearby candidates without deleting them."""
    groups = defaultdict(list)
    records = []
    for number, issue in enumerate(issues, 1):
        record = {
            "id": f"issue-{number:04d}",
            "category": issue.category, "message": issue.message,
            "page": issue.page, "bbox": issue.bbox,
            "related_bboxes": issue.related_bboxes,
            "candidate": issue.candidate, "review_status": issue.review_status,
            "level": issue.level,
        }
        records.append(record)
        if issue.bbox:
            x0, y0, x1, y1 = issue.bbox
            # One-inch spatial bins are review groups, not collision judgments.
            key = (issue.page, issue.category, int((x0+x1)/144), int((y0+y1)/144))
            groups[key].append(record)
    review_groups = []
    for (page, category, _x, _y), group in groups.items():
        boxes = [r["bbox"] for r in group]
        review_groups.append({
            "page": page, "category": category, "count": len(group),
            "bbox": [min(b[0] for b in boxes), min(b[1] for b in boxes),
                     max(b[2] for b in boxes), max(b[3] for b in boxes)],
            "issue_ids": [r["id"] for r in group],
            "review_status": "needs-visual-review",
        })
    errors = [r for r in records if r["level"] == "ERROR"]
    warns = [r for r in records if r["level"] == "WARN"]
    return {
        "file": filepath,
        "status": ("incomplete" if not complete else
                   "needs-visual-review" if records else "no-candidates-found"),
        "visual_review_required": True,
        "coordinate_system": "PDF points, top-left origin; bbox=[x0,top,x1,bottom]; page is one-based",
        "errors": errors, "warnings": warns,
        "review_groups": review_groups,
        "coverage": {
            "complete": complete, "pages_checked": len(coverage), "pages": coverage,
            "limitations": [
                "Text bounding boxes do not establish glyph-ink collisions; fractions, scripts and kerning require visual triage.",
                "Node/container selection is geometric; exclusions and their boxes are listed per page.",
                "Bezier paths use control-polygon approximations; this is not pixel-level rendering validation.",
            ],
        },
        "summary": {
            "error_count": len(errors), "warning_count": len(warns),
            "candidate_count": sum(r["candidate"] for r in records),
            "counts_by_category": dict(Counter(r["category"] for r in records)),
            "review_group_count": len(review_groups),
        },
    }


def main(argv=None):
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filepath")
    parser.add_argument("--json", action="store_true", help="Full structured findings")
    parser.add_argument("--max-per-category", type=int, default=8,
                        help="Console examples per category (default 8; JSON is never truncated)")
    args = parser.parse_args(argv)
    coverage = []
    complete = True
    uncompleted_pages = []
    try:
        issues = validate_pdf(args.filepath, coverage)
    except (IncompleteCheck, ImportError, OSError, ValueError, RuntimeError) as exc:
        complete = False
        uncompleted_pages = list(getattr(exc, "uncompleted_pages", []))
        issues = list(getattr(exc, "partial_issues", []))
        issues.append(Issue("ERROR", "check-incomplete", str(exc),
                            page=getattr(exc, "failed_page", None), candidate=False,
                            review_status="not-run"))
    report = build_report(args.filepath, issues, coverage, complete)
    report["coverage"]["uncompleted_pages"] = uncompleted_pages
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"PDF 几何候选报告: {args.filepath}")
        print(f"状态: {report['status']}；已检查 {len(coverage)} 页")
        by_category = defaultdict(list)
        for issue in issues:
            by_category[issue.category].append(issue)
        for category, members in by_category.items():
            print(f"\n[{category}] 共 {len(members)} 项")
            limit = max(0, args.max_per_category)
            for issue in members[:limit]:
                where = f"page={issue.page}, bbox={issue.bbox}"
                print(f"  [{issue.level}; {issue.review_status}; {where}] {issue.message}")
            omitted = len(members) - limit
            if omitted > 0:
                print(f"  另 {omitted} 项；完整坐标与局部分组见 --json。")
        summary = report["summary"]
        print(f"\n合计: {summary['error_count']} 错误候选/检测错误，"
              f"{summary['warning_count']} 警告；{summary['review_group_count']} 局部复核组。")
        print("自动几何检测不能替代渲染目视复核；未发现候选也不等于版式已通过。")
    return 2 if (not complete or report["errors"]) else (1 if issues else 0)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
