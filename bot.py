"""Auto-play the match-3 event.

Stops on F8, when the game loses focus, or when the board has been unreadable
for --idle seconds (level finished, popup, etc.).

    python bot.py --dry         print the board and chosen move, touch nothing
    python bot.py --moves 3     play at most 3 moves
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
from win import find_window

VK_F8 = 0x77


def stable_board(hwnd, tries=7, gap=0.18):
    """Return (colors, specials) once two consecutive reads agree, else None."""
    prev = None
    for _ in range(tries):
        g, s = vision.read_board(grab(hwnd))
        if prev == g:
            return g, s
        prev = g
        time.sleep(gap)
    return None


def unknown_count(g):
    return sum(k == vision.X for row in g for k in row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--moves", type=int, default=100)
    ap.add_argument("--idle", type=float, default=12.0)
    ap.add_argument("--settle", type=float, default=2.2)
    args = ap.parse_args()
    hwnd = find_window()
    if not hwnd:
        sys.exit("game window not found")
    if args.dry:
        res = stable_board(hwnd)
        if res is None:
            sys.exit("board never settled")
        g, s = res
        print(vision.fmt(g, s))
        print("move", solver.best_move(g, s))
        return
    saved = win32api.GetCursorPos()
    if not inputs.focus(hwnd):
        sys.exit("could not focus the game")
    played, last_seen, banned, prev_g, last = 0, time.time(), set(), None, None
    try:
        while played < args.moves:
            if win32api.GetAsyncKeyState(VK_F8) & 0x8000:
                print("stopped: F8")
                break
            if win32gui.GetForegroundWindow() != hwnd:
                print("stopped: game lost focus")
                break
            res = stable_board(hwnd)
            if res is None or unknown_count(res[0]) > 8:
                if time.time() - last_seen > args.idle:
                    print("stopped: board not readable")
                    break
                time.sleep(0.5)
                continue
            last_seen = time.time()
            g, s = res
            if g == prev_g:   # the last swap changed nothing
                banned.add(last)
            else:
                banned.clear()
            mv, val = solver.best_move(g, s, banned)
            if mv is None:
                print("no move found\n" + vision.fmt(g, s))
                break
            a, b = mv
            print(f"#{played + 1} {a}->{b} value {val:.1f}", flush=True)
            inputs.drag(hwnd, *vision.cell_xy(*a), *vision.cell_xy(*b))
            played += 1
            prev_g, last = g, mv
            time.sleep(args.settle)
    finally:
        win32api.SetCursorPos(saved)
    print("played", played)


if __name__ == "__main__":
    main()
