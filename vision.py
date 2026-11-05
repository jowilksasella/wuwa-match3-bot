"""Read the 8x7 board from a 1280x720 BGR frame."""
import cv2
import numpy as np

ROWS, COLS = 7, 8
X0, DX, Y0, DY = 620.0, 82.3, 130.0, 81.7

G, M, R, B, W, U, X = 0, 1, 2, 3, 4, 5, -1   # green, mask, red, blue, white, ultimate, unknown
NONE, BOMB, CROSS = 0, 1, 2
NAMES = {G: "G", M: "M", R: "R", B: "B", W: "W", U: "U", X: "?"}


def cell_xy(r, c):
    return int(round(X0 + c * DX)), int(round(Y0 + r * DY))


def _frac(h, lo, hi):
    return float(((h >= lo) & (h < hi)).mean()) if h.size else 0.0


def classify(hsv, x, y):
    c = hsv[y - 26:y + 26, x - 26:x + 26].reshape(-1, 3)
    white = float(((c[:, 1] < 50) & (c[:, 2] > 200)).mean())
    m = (c[:, 1] > 70) & (c[:, 2] > 100)
    cover = float(m.mean())
    if cover + white < 0.25:
        return X
    h = c[m, 0]
    pink = _frac(h, 135, 172)
    if pink > 0.30 and white > 0.08:
        return U
    if white > 0.25:
        return W
    scores = {
        R: _frac(h, 0, 13) + _frac(h, 172, 180),
        M: _frac(h, 13, 33) + _frac(h, 115, 150),
        G: _frac(h, 35, 85),
        B: _frac(h, 85, 115),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0.35 else X


def _yellow(hsv, x0, y0, x1, y1):
    p = hsv[y0:y1, x0:x1].reshape(-1, 3)
    return int(((p[:, 0] > 20) & (p[:, 0] < 35) & (p[:, 1] > 170) & (p[:, 2] > 210)).sum())


def special_of(hsv, x, y):
    # The idle hint draws a yellow frame around whole cells; an arrow is yellow
    # only at the middle of an edge, so a yellow edge away from the middle is a frame.
    # The band sits on this cell's own frame so a neighbour's frame is not counted.
    if (_yellow(hsv, x - 26, y - 41, x - 12, y - 34) + _yellow(hsv, x + 12, y + 34, x + 26, y + 41)
            + _yellow(hsv, x - 41, y + 12, x - 34, y + 26) + _yellow(hsv, x + 34, y - 26, x + 41, y - 12)) >= 16:
        return NONE
    edges = ((-10, -46, 10, -32), (-10, 32, 10, 46), (-46, -10, -32, 10), (32, -10, 46, 10))
    edge = sum(1 for b in edges if _yellow(hsv, x + b[0], y + b[1], x + b[2], y + b[3]) >= 8)
    corners = ((-42, -42, -28, -28), (28, -42, 42, -28), (-42, 28, -28, 42), (28, 28, 42, 42))
    corner = sum(1 for b in corners if _yellow(hsv, x + b[0], y + b[1], x + b[2], y + b[3]) >= 8)
    if edge >= 3:
        return CROSS
    if corner >= 3:
        return BOMB
    return NONE


def read_board(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    colors, specials = [], []
    for r in range(ROWS):
        cr, sr = [], []
        for c in range(COLS):
            x, y = cell_xy(r, c)
            k = classify(hsv, x, y)
            cr.append(k)
            sr.append(special_of(hsv, x, y) if k not in (X, U) else NONE)
        colors.append(cr)
        specials.append(sr)
    return colors, specials


def fmt(colors, specials):
    mark = {NONE: " ", BOMB: "*", CROSS: "+"}
    return "\n".join(" ".join(NAMES[k] + mark[s] for k, s in zip(a, b))
                     for a, b in zip(colors, specials))
