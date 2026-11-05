"""Read the 8x7 board from a 1280x720 BGR frame on the local GPU.

Plain colour thresholds run as tensor operations. There is no model and no
network access; PyTorch is used only as a GPU array library.
"""
import os

import cv2
import numpy as np
import torch

ROWS, COLS = 7, 8
X0, DX, Y0, DY = 620.0, 82.3, 130.0, 81.7

# green, mask, red, blue, white, ultimate, energy bottle, ice, hourglass, unknown
G, M, R, B, W, U, E, ICE, HOUR, X = 0, 1, 2, 3, 4, 5, 6, 7, 8, -1
NONE, BOMB, CROSS = 0, 1, 2
HEARTS = 10     # a bottle's special value is HEARTS + its remaining hits
CHAIN = 100     # a chained piece adds CHAIN x its remaining uses to its special value
NAMES = {G: "G", M: "M", R: "R", B: "B", W: "W", U: "U", E: "E", ICE: "I", HOUR: "H", X: "?"}

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
DEVICE_NAME = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU (no CUDA GPU found)"


def cell_xy(r, c):
    return int(round(X0 + c * DX)), int(round(Y0 + r * DY))


_CX = torch.tensor([cell_xy(r, c)[0] for r in range(ROWS) for c in range(COLS)], device=DEVICE)
_CY = torch.tensor([cell_xy(r, c)[1] for r in range(ROWS) for c in range(COLS)], device=DEVICE)


def _hsv(bgr):
    """BGR uint8 tensor to float HSV on OpenCV's 8-bit scale (H 0-179, S and V 0-255)."""
    t = bgr.float()
    b, g, r = t[..., 0], t[..., 1], t[..., 2]
    v = t.max(-1).values
    d = v - t.min(-1).values
    safe = d.clamp(min=1e-6)
    h = torch.where(v == r, 60 * (g - b) / safe,
                    torch.where(v == g, 120 + 60 * (b - r) / safe, 240 + 60 * (r - g) / safe))
    h = torch.where(d == 0, torch.zeros_like(h), h)
    h = torch.round(torch.where(h < 0, h + 360, h) / 2) % 180
    s = torch.round(255 * d / v.clamp(min=1e-6))
    return torch.stack((h, s, v), -1)


def _patches(t, box):
    """Cut the same (x0, y0, x1, y1) offset box out of every cell; returns one row per cell."""
    x0, y0, x1, y1 = box
    ys = _CY[:, None, None] + torch.arange(y0, y1, device=DEVICE)[None, :, None]
    xs = _CX[:, None, None] + torch.arange(x0, x1, device=DEVICE)[None, None, :]
    p = t[ys, xs]
    return p.reshape(p.shape[0], (y1 - y0) * (x1 - x0), *p.shape[3:])


def _classify(hsv):
    c = _patches(hsv, (-26, -26, 26, 26))
    h, s, v = c[..., 0], c[..., 1], c[..., 2]
    white = ((s < 50) & (v > 200)).float().mean(1)
    m = (s > 70) & (v > 100)
    n = m.sum(1).clamp(min=1).float()

    def frac(lo, hi):
        return ((h >= lo) & (h < hi) & m).sum(1).float() / n

    pink = frac(135, 172)
    cyan = frac(85, 115)
    # Stack order matches the class ids G=0, M=1, R=2, B=3.
    scores = torch.stack((frac(35, 85), frac(13, 33) + frac(115, 150),
                          frac(0, 13) + frac(172, 180), frac(85, 115)), 1)
    best, top = scores.argmax(1), scores.max(1).values
    out = torch.where(top > 0.35, best, torch.full_like(best, X))
    out = torch.where(white > 0.25, torch.full_like(out, W), out)
    # Ice is one flat teal (hue 89-92); the blue whale peaks near 98 and has warm pixels.
    out = torch.where(frac(85, 96) > 0.6, torch.full_like(out, ICE), out)
    # The hourglass is the only piece with a large area of bright gold (>= 0.25, others <= 0.07).
    gold = ((h >= 18) & (h < 33) & (s > 120) & (v > 170)).float().mean(1)
    out = torch.where(gold > 0.18, torch.full_like(out, HOUR), out)
    # Both are pink with white highlights: only the ultimate has cyan stripes.
    out = torch.where((pink > 0.30) & (white > 0.08) & (cyan >= 0.03), torch.full_like(out, U), out)
    out = torch.where((pink > 0.45) & (white > 0.15) & (cyan < 0.03), torch.full_like(out, E), out)
    return torch.where(m.float().mean(1) + white < 0.25, torch.full_like(out, X), out)


def _hearts(hsv):
    """Count filled heart slots above a bottle; a used slot is empty, not dimmed."""
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    gold = (h > 15) & (h < 35) & (s > 150) & (v > 180)
    slots = ((-17, -33, -3, -14), (0, -33, 14, -14), (16, -33, 30, -14))
    return sum((_patches(gold, b).sum(1) >= 20).int() for b in slots).clamp(min=1)


def _specials(hsv):
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    yellow = (h > 20) & (h < 35) & (s > 170) & (v > 210)

    def count(box):
        return _patches(yellow, box).sum(1)

    # The idle hint draws a yellow frame around whole cells; an arrow is yellow
    # only at the middle of an edge, so a yellow edge away from the middle is a frame.
    # The band sits on this cell's own frame so a neighbour's frame is not counted.
    frame = (count((-26, -41, -12, -34)) + count((12, 34, 26, 41))
             + count((-41, 12, -34, 26)) + count((34, -26, 41, -12))) >= 16
    edges = ((-10, -46, 10, -32), (-10, 32, 10, 46), (-46, -10, -32, 10), (32, -10, 46, 10))
    corners = ((-42, -42, -28, -28), (28, -42, 42, -28), (-42, 28, -28, 42), (28, 28, 42, 42))
    edge = sum((count(b) >= 8).int() for b in edges)
    corner = sum((count(b) >= 8).int() for b in corners)
    out = torch.where(corner >= 3, torch.full_like(edge, BOMB), torch.full_like(edge, NONE))
    out = torch.where(edge >= 3, torch.full_like(edge, CROSS), out)
    return torch.where(frame, torch.full_like(edge, NONE), out)


def _crimson(hsv):
    """The chain badge's star, a pure crimson no ordinary piece uses."""
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return ((h >= 170) | (h <= 1)) & (s > 190) & (v > 180)


def _white(hsv):
    return (hsv[..., 1] < 70) & (hsv[..., 2] > 190)


def _digit_window(white, cx, cy):
    """The digit sits a fixed distance right of the star's centre."""
    return white[cy - 6:cy + 8, cx + 6:cx + 17]


@torch.inference_mode()
def _load_digits():
    digits = {}
    for n in (1, 2, 3):
        path = os.path.join(_ASSETS, f"chain{n}.png")
        t = torch.from_numpy(cv2.imdecode(np.fromfile(path, np.uint8), 1)).to(DEVICE)
        hsv = _hsv(t)
        ys, xs = _crimson(hsv).nonzero(as_tuple=True)
        digits[n] = _digit_window(_white(hsv), int(xs.float().mean()), int(ys.float().mean()))
    return digits


def _read_digit(white, cx, cy):
    """Match the digit against the saved badges, allowing a pixel of drift."""
    scores = {}
    for n, tmpl in _DIGITS.items():
        scores[n] = min(int((_digit_window(white, cx + dx, cy + dy) != tmpl).sum())
                        for dx in (-1, 0, 1) for dy in (-1, 0, 1))
    return min(scores, key=scores.get)


def _chains(hsv):
    """Remaining uses of each cell's chain badge, 0 for no badge."""
    crimson = _crimson(hsv)
    box = (6, -28, 24, -8)
    found = (_patches(crimson, box).sum(1) >= 20).nonzero().flatten().tolist()
    out = torch.zeros(ROWS * COLS, dtype=torch.long, device=DEVICE)
    white = _white(hsv)
    for i in found:
        x0, y0 = int(_CX[i]) + box[0], int(_CY[i]) + box[1]
        ys, xs = crimson[y0:int(_CY[i]) + box[3], x0:int(_CX[i]) + box[2]].nonzero(as_tuple=True)
        out[i] = _read_digit(white, x0 + int(xs.float().mean()), y0 + int(ys.float().mean()))
    return out


@torch.inference_mode()
def read_board(img):
    hsv = _hsv(torch.from_numpy(img).to(DEVICE))
    k = _classify(hsv)
    s = _specials(hsv)
    s = torch.where((k == X) | (k == U) | (k == ICE) | (k == HOUR), torch.full_like(s, NONE), s)
    s = torch.where(k == E, HEARTS + _hearts(hsv), s) + CHAIN * _chains(hsv)
    k, s = k.tolist(), s.tolist()
    return ([k[r * COLS:(r + 1) * COLS] for r in range(ROWS)],
            [s[r * COLS:(r + 1) * COLS] for r in range(ROWS)])


_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
_DIGITS = _load_digits()
_BTN_BOX = (20, 52, 950, 1082)   # y0, y1, x0, x1 of the effects-panel button


def _button_text(bgr):
    """White lettering of the button. Its colour changes with the character theme; the text does not."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    return (hsv[..., 1] < 60) & (hsv[..., 2] > 215)


_btn = _button_text(cv2.imdecode(np.fromfile(os.path.join(_ASSETS, "button.png"), np.uint8), 1))


def in_level(img):
    """True only on the live board: the HUD button and the panel border are both undimmed."""
    y0, y1, x0, x1 = _BTN_BOX
    if (_button_text(img[y0:y1, x0:x1]) != _btn).mean() > 0.05:
        return False
    border = (np.median(img[680:684, 600:1220].reshape(-1, 3), axis=0),
              np.median(img[120:640, 1254:1258].reshape(-1, 3), axis=0))
    return all(np.abs(b - ref).max() <= 18 for b, ref in zip(border, ((66, 55, 134), (74, 57, 141))))


def turn_crop(img):
    """The digits of the remaining-turns counter, which changes only when a move has fully resolved."""
    return img[118:148, 156:192].astype(int)


def turn_changed(a, b):
    return float(np.abs(a - b).mean()) > 14


def fmt(colors, specials):
    mark = {NONE: " ", BOMB: "*", CROSS: "+"}

    def cell(k, s):
        base = s % CHAIN
        return f"{NAMES[k]}{mark.get(base, str(base - HEARTS))}{s // CHAIN or ' '}"

    return "\n".join(" ".join(cell(k, s) for k, s in zip(a, b)) for a, b in zip(colors, specials))
