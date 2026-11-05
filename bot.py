"""Auto-play the match-3 event. Runs entirely on this PC, with no network access.

Pick a level yourself: the bot starts when a board appears, waits again after
the level ends, and only acts while the game is the foreground window.
F8 quits.

    python bot.py               stay running and play every level you open
    python bot.py --dry         print the board and chosen move, touch nothing
    python bot.py --moves 3     quit after 3 moves
"""
import argparse
import sys
import time

import win32api
import win32gui

import inputs
import solver
import vision
from capture import grab
from win import find_window, geometry

VK_F8 = 0x77
MAX_UNKNOWN = 8
TURN_TIMEOUT = 6.0     # a rejected swap never changes the counter
_last_status = None


def status(text):
    """Print a state line only when the state changes."""
    global _last_status
    if text != _last_status:
        print(time.strftime("[%H:%M:%S]"), text, flush=True)
        _last_status = text


def f8_pressed():
    return bool(win32api.GetAsyncKeyState(VK_F8) & 0x8001)


def wait(seconds):
    """Sleep while watching F8; returns True when F8 was pressed."""
    end = time.time() + seconds
    while time.time() < end:
        if f8_pressed():
            return True
        time.sleep(0.05)
    return False


def stable_board(hwnd, tries=7, gap=0.18):
    """Return (colors, specials) once three consecutive reads agree, else None.

    Special-piece arrows pulse, so a piece counts as special if any read saw it.
    """
    prev, agree, seen = None, 0, None
    for _ in range(tries + 2):
        g, s = vision.read_board(grab(hwnd))
        if g == prev:
            agree += 1
            seen = [[max(a, b) for a, b in zip(x, y)] for x, y in zip(seen, s)]
        else:
            agree, seen = 0, s
        if agree >= 2:
            return g, seen
        prev = g
        time.sleep(gap)
    return None


def unknown_count(g):
    return sum(k == vision.X for row in g for k in row)


def bottles(g, s):
    return sorted((s[r][c] % vision.CHAIN - vision.HEARTS for r in range(vision.ROWS) for c in range(vision.COLS)
                   if g[r][c] == vision.E), reverse=True)


def wait_resolved(hwnd, before):
    """After a drag, wait for the turn counter to change.

    The game drops input while a chain resolves, and chains pause long enough to
    look settled, so elapsed time and a still board do not prove the turn is over.
    Returns "done", "ended" (left the level), "timeout" (swap rejected) or "stop" (F8).
    """
    end = time.time() + TURN_TIMEOUT
    while time.time() < end:
        if wait(0.15):
            return "stop"
        img = grab(hwnd)
        if not vision.in_level(img):
            return "ended"
        if vision.turn_changed(before, vision.turn_crop(img)):
            return "done"
    return "timeout"


def ready(hwnd):
    """Name what blocks play right now, or return None when the bot may act."""
    if not win32gui.IsWindow(hwnd):
        return "遊戲視窗已關閉"
    if win32gui.GetForegroundWindow() != hwnd:
        return "暫停：遊戲不在前景"
    if geometry(hwnd)[2:] != (1280, 720):
        return "暫停：遊戲畫面必須是 1280x720"
    if not vision.in_level(grab(hwnd)):
        return "等待進入關卡"
    return None


def play(hwnd, max_moves, settle, trace=False):
    played, banned, prev_g, last = 0, set(), None, None
    while not max_moves or played < max_moves:
        if f8_pressed():
            return played
        blocked = ready(hwnd)
        if blocked:
            prev_g = None
            status(blocked)
            if wait(0.4):
                return played
            continue
        res = stable_board(hwnd)
        if res is None:
            continue
        g, s = res
        missing = unknown_count(g)
        if missing > MAX_UNKNOWN:
            status(f"等待：有 {missing} 格認不出")
            if wait(0.4):
                return played
            continue
        if g == prev_g:      # the last swap changed nothing
            banned.add(last)
        else:
            banned.clear()
        mv, val = solver.best_move(g, s, banned)
        if mv is None:
            status("目前找不到可走的一步")
            banned.clear()
            if wait(1.0):
                return played
            continue
        if ready(hwnd):      # a popup or focus change may have arrived during the reads
            continue
        status("關卡進行中")
        a, b = mv
        played += 1
        left = bottles(g, s)
        if trace:
            print(vision.fmt(g, s), flush=True)
        print(f"  第 {played} 步 {a}->{b} 評分 {val:.1f}" + (f" 能量瓶剩餘心數 {left}" if left else ""), flush=True)
        before = vision.turn_crop(grab(hwnd))
        inputs.drag(hwnd, *vision.cell_xy(*a), *vision.cell_xy(*b))
        prev_g, last = g, mv
        result = wait_resolved(hwnd, before)
        if result == "stop" or wait(settle):
            return played
    return played


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--moves", type=int, default=0, help="quit after N moves; 0 = no limit")
    ap.add_argument("--settle", type=float, default=1.2, help="seconds to wait after the turn counter changes")
    ap.add_argument("--trace", action="store_true", help="print the board before every move")
    args = ap.parse_args()
    print("讀圖裝置:", vision.DEVICE_NAME, flush=True)
    hwnd = find_window()
    while not hwnd:
        status("等待遊戲視窗")
        if wait(1.0):
            return
        hwnd = find_window()
    if args.dry:
        res = stable_board(hwnd)
        if res is None:
            sys.exit("board never settled")
        g, s = res
        print("in_level", vision.in_level(grab(hwnd)))
        print(vision.fmt(g, s))
        print("move", solver.best_move(g, s))
        return
    print("已啟動，按 F8 結束。請在遊戲裏揀關卡。", flush=True)
    played = play(hwnd, args.moves, args.settle, args.trace)
    print("結束，共走", played, "步")


if __name__ == "__main__":
    main()
