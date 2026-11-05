"""One-ply move search with a forward simulation of the known rules.

Rules (in-game effects panel):
  straight 4          -> bomb: clears 3x3 when eliminated
  T/L shape, 5+ cells -> cross: clears its row and column when eliminated
  straight 5+         -> ultimate: swapped with a piece, clears that piece's type;
                         two ultimates swapped clear the whole board
  energy bottle       -> removed after three eliminations around it, gives 80 energy;
                         it is the goal of some levels
  ice                 -> removed by one elimination around it; never falls or moves

Refill is unknown, so the simulation applies gravity without new pieces.
Bottles and ice are never dragged and never match. "Around" is modelled as the
four orthogonal neighbours, with at most one hit per elimination step.
"""
from vision import ROWS, COLS, U, E, ICE, X, NONE, BOMB, CROSS, HEARTS

EMPTY = -2
BONUS = {BOMB: 4.0, CROSS: 7.0, "U": 12.0}
BOTTLE_HIT, BOTTLE_POP = 8.0, 16.0     # worth more than any plain match
ICE_HIT = 3.0                          # opens the board; about one extra matched piece each way
UNMATCHABLE = (U, E, ICE)
UNDRAGGABLE = (X, E, ICE)
UNBLASTABLE = (X, EMPTY, E, ICE)       # these take hits through _hit instead


def _runs(g):
    runs = []
    for r in range(ROWS):
        c = 0
        while c < COLS:
            k = g[r][c]
            e = c
            while e + 1 < COLS and g[r][e + 1] == k:
                e += 1
            if k >= 0 and k not in UNMATCHABLE and e - c >= 2:
                runs.append(("h", [(r, i) for i in range(c, e + 1)]))
            c = e + 1
    for c in range(COLS):
        r = 0
        while r < ROWS:
            k = g[r][c]
            e = r
            while e + 1 < ROWS and g[e + 1][c] == k:
                e += 1
            if k >= 0 and k not in UNMATCHABLE and e - r >= 2:
                runs.append(("v", [(i, c) for i in range(r, e + 1)]))
            r = e + 1
    return runs


def _groups(g):
    groups = []
    for d, cells in _runs(g):
        s = set(cells)
        merged = [(d, cells)]
        rest = []
        for gr in groups:
            if gr["cells"] & s:
                s |= gr["cells"]
                merged += gr["runs"]
            else:
                rest.append(gr)
        rest.append({"cells": s, "runs": merged})
        groups = rest
    return groups


def _kind(gr):
    longest = max(len(c) for _, c in gr["runs"])
    dirs = {d for d, _ in gr["runs"]}
    if longest >= 5:
        return "U"
    if len(dirs) == 2 and len(gr["cells"]) >= 5:
        return CROSS
    if longest == 4:
        return BOMB
    return None


def _blast(g, s, clear):
    """Grow a clear set through special pieces; bottles in the area are kept for _hit."""
    todo = list(clear)
    seen = set(clear)
    while todo:
        r, c = todo.pop()
        kind = s[r][c]
        if kind == BOMB:
            area = [(r + a, c + b) for a in (-1, 0, 1) for b in (-1, 0, 1)]
        elif kind == CROSS:
            area = [(r, i) for i in range(COLS)] + [(i, c) for i in range(ROWS)]
        else:
            continue
        for p in area:
            if 0 <= p[0] < ROWS and 0 <= p[1] < COLS and p not in seen and g[p[0]][p[1]] not in UNBLASTABLE:
                seen.add(p)
                todo.append(p)
    return seen


def _hit(g, s, cleared):
    """Apply this step to each bottle and ice block it touches; returns the score."""
    bonus = 0.0
    for r in range(ROWS):
        for c in range(COLS):
            if g[r][c] not in (E, ICE) or (r, c) in cleared:
                continue
            near = ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1))
            if not any(p in cleared for p in near):
                continue
            if g[r][c] == ICE:
                g[r][c] = EMPTY
                bonus += ICE_HIT
                continue
            s[r][c] -= 1
            bonus += BOTTLE_HIT
            if s[r][c] <= HEARTS:
                g[r][c], s[r][c] = EMPTY, NONE
                bonus += BOTTLE_POP
    return bonus


def _gravity(g, s):
    for c in range(COLS):
        w = ROWS - 1
        for r in range(ROWS - 1, -1, -1):
            if g[r][c] in (X, ICE):
                w = r - 1
            elif g[r][c] != EMPTY:
                if w != r:
                    g[w][c], s[w][c] = g[r][c], s[r][c]
                    g[r][c], s[r][c] = EMPTY, NONE
                w -= 1


def _clear(g, s, cells):
    for r, c in cells:
        g[r][c], s[r][c] = EMPTY, NONE


def simulate(g0, s0, a, b):
    """Return the score of swapping a and b, or None when the swap does nothing."""
    g = [row[:] for row in g0]
    s = [row[:] for row in s0]
    (r1, c1), (r2, c2) = a, b
    k1, k2 = g[r1][c1], g[r2][c2]
    if k1 in UNDRAGGABLE or k2 in UNDRAGGABLE:
        return None
    total = bonus = 0.0
    if U in (k1, k2):
        if k1 == k2:
            cells = {(r, c) for r in range(ROWS) for c in range(COLS) if g[r][c] not in UNBLASTABLE}
        else:
            target = k2 if k1 == U else k1
            cells = {(r, c) for r in range(ROWS) for c in range(COLS) if g[r][c] == target}
            cells |= {a, b}
        cells = _blast(g, s, cells)
        total += len(cells)
        bonus += _hit(g, s, cells)
        _clear(g, s, cells)
        _gravity(g, s)
    else:
        g[r1][c1], g[r2][c2] = k2, k1
        s[r1][c1], s[r2][c2] = s[r2][c2], s[r1][c1]
        if not _groups(g):
            return None
    first = True
    while True:
        groups = _groups(g)
        if not groups:
            break
        clear, spawns = set(), []
        for gr in groups:
            clear |= gr["cells"]
            kind = _kind(gr)
            if kind is None:
                continue
            anchor = next((p for p in (a, b) if first and p in gr["cells"]), max(gr["cells"]))
            spawns.append((anchor, kind, g[anchor[0]][anchor[1]]))
            bonus += BONUS[kind]
        hit = _blast(g, s, clear)
        total += len(hit)
        bonus += _hit(g, s, hit)
        _clear(g, s, hit)
        for (r, c), kind, color in spawns:
            if kind == "U":
                g[r][c], s[r][c] = U, NONE
            else:
                g[r][c], s[r][c] = color, kind
        _gravity(g, s)
        first = False
    depth = (r1 + r2) / 2 / (ROWS - 1)   # lower moves shake more of the board
    return total + bonus + 0.3 * depth


def best_move(g, s, banned=()):
    best, best_score = None, -1.0
    for r in range(ROWS):
        for c in range(COLS):
            for nb in ((r, c + 1), (r + 1, c)):
                if nb[0] >= ROWS or nb[1] >= COLS or ((r, c), nb) in banned:
                    continue
                v = simulate(g, s, (r, c), nb)
                if v is not None and v > best_score:
                    best, best_score = ((r, c), nb), v
    return best, best_score
