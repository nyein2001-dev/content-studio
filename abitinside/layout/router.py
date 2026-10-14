"""Orthogonal and straight connector routing around text and icons."""
from __future__ import annotations

import heapq
import math

from layout.errors import LayoutError
from layout.geom import Rect, segment_hits_rect


def _outside(rect: Rect, ox: float, oy: float) -> tuple[float, float]:
    if ox <= rect.cx:
        x = rect.x
    else:
        x = rect.right
    if oy <= rect.cy:
        y = rect.y
    else:
        y = rect.bottom
    if abs(ox - rect.cx) * rect.h >= abs(oy - rect.cy) * max(rect.w, 1):
        y = min(max(oy, rect.y), rect.bottom)
        x = rect.x if ox <= rect.cx else rect.right
    else:
        x = min(max(ox, rect.x), rect.right)
        y = rect.y if oy <= rect.cy else rect.bottom
    # Step just outside so the path can leave the box.
    if abs(x - rect.x) <= 0.1:
        x -= 1.0
    elif abs(x - rect.right) <= 0.1:
        x += 1.0
    if abs(y - rect.y) <= 0.1:
        y -= 1.0
    elif abs(y - rect.bottom) <= 0.1:
        y += 1.0
    return x, y


def anchors(a: Rect, b: Rect) -> tuple[tuple[float, float], tuple[float, float]]:
    start = _outside(a, b.cx, b.cy)
    end = _outside(b, a.cx, a.cy)
    return start, end


def _hits(a, b, obstacles: list[Rect]) -> bool:
    for rect in obstacles:
        if segment_hits_rect(a[0], a[1], b[0], b[1], rect):
            return True
    return False


def route(
    scene: str,
    start: tuple[float, float],
    end: tuple[float, float],
    obstacles: list[Rect],
    bounds: Rect,
    step: int,
    mode: str = "orthogonal",
) -> tuple[tuple[float, float], ...]:
    if mode == "straight" and not _hits(start, end, obstacles):
        return (start, end)
    bends = ((end[0], start[1]), (start[0], end[1]))
    for mid in bends:
        mid_box = Rect(mid[0], mid[1], 1, 1)
        if not bounds.contains(mid_box, eps=step):
            continue
        if not _hits(start, mid, obstacles) and not _hits(mid, end, obstacles):
            return (start, mid, end)
    if mode == "straight" and not _hits(start, end, obstacles):
        return (start, end)
    path = _astar(start, end, obstacles, bounds, step)
    if path is None:
        raise LayoutError(
            scene, "R08",
            "no connector route avoids text and icons",
            "Move the two endpoints further apart in the scene DSL, or remove the connector. "
            "The engine will not draw a line through a label.",
        )
    return tuple(path)


def _astar(start, end, obstacles, bounds: Rect, step: int):
    def cell(point):
        return (
            int(math.floor((point[0] - bounds.x) / step)),
            int(math.floor((point[1] - bounds.y) / step)),
        )

    cols = max(1, int(math.floor(bounds.w / step)))
    rows = max(1, int(math.floor(bounds.h / step)))

    def inside(c):
        return 0 <= c[0] < cols and 0 <= c[1] < rows

    def center(c):
        return (bounds.x + (c[0] + 0.5) * step, bounds.y + (c[1] + 0.5) * step)

    blocked: set[tuple[int, int]] = set()
    for rect in obstacles:
        x0 = max(0, int(math.floor((rect.x - bounds.x) / step)))
        x1 = min(cols - 1, int(math.floor((rect.right - bounds.x) / step)))
        y0 = max(0, int(math.floor((rect.y - bounds.y) / step)))
        y1 = min(rows - 1, int(math.floor((rect.bottom - bounds.y) / step)))
        for gy in range(y0, y1 + 1):
            for gx in range(x0, x1 + 1):
                blocked.add((gx, gy))

    start_c = cell(start)
    goal_c = cell(end)
    if not inside(start_c) or not inside(goal_c):
        return None
    blocked.discard(start_c)
    blocked.discard(goal_c)

    def h(c):
        return abs(c[0] - goal_c[0]) + abs(c[1] - goal_c[1])

    queue = [(h(start_c), 0, start_c)]
    came: dict[tuple[int, int], tuple[int, int] | None] = {start_c: None}
    cost = {start_c: 0}
    while queue:
        _, dist, current = heapq.heappop(queue)
        if current == goal_c:
            break
        if dist != cost.get(current):
            continue
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (current[0] + dx, current[1] + dy)
            if not inside(nxt) or nxt in blocked:
                continue
            new_cost = dist + 1
            if new_cost < cost.get(nxt, 1_000_000):
                cost[nxt] = new_cost
                came[nxt] = current
                heapq.heappush(queue, (new_cost + h(nxt), new_cost, nxt))
    if goal_c not in came:
        return None
    cells = []
    cursor = goal_c
    while cursor is not None:
        cells.append(cursor)
        cursor = came[cursor]
    cells.reverse()
    points = [start]
    for item in cells[1:-1]:
        points.append(center(item))
    points.append(end)
    return _simplify(points)


def _simplify(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) < 3:
        return points
    kept = [points[0]]
    for point in points[1:-1]:
        prev = kept[-1]
        # Drop a point that continues the same orthogonal direction.
        if (abs(prev[0] - point[0]) < 0.1) or (abs(prev[1] - point[1]) < 0.1):
            if len(kept) >= 2:
                older = kept[-2]
                same_x = abs(older[0] - prev[0]) < 0.1 and abs(prev[0] - point[0]) < 0.1
                same_y = abs(older[1] - prev[1]) < 0.1 and abs(prev[1] - point[1]) < 0.1
                if same_x or same_y:
                    kept[-1] = point
                    continue
        kept.append(point)
    kept.append(points[-1])
    return kept
