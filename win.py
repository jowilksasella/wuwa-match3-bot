"""Find the game window and report geometry."""
import ctypes, sys
from ctypes import wintypes
import win32gui, win32process, win32con, win32api

ctypes.windll.shcore.SetProcessDpiAwareness(2)
EXE = "Client-Win64-Shipping"

def find_window():
    import psutil
    pids = {p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").startswith(EXE)}
    found = []
    def cb(h, _):
        if not win32gui.IsWindowVisible(h):
            return True
        _, pid = win32process.GetWindowThreadProcessId(h)
        if pid in pids:
            l, t, r, b = win32gui.GetClientRect(h)
            if r - l > 100:
                found.append(h)
        return True
    win32gui.EnumWindows(cb, None)
    return found[0] if found else None

def geometry(h):
    l, t, r, b = win32gui.GetClientRect(h)
    x, y = win32gui.ClientToScreen(h, (0, 0))
    return x, y, r - l, b - t

if __name__ == "__main__":
    h = find_window()
    print("hwnd", h)
    if h:
        print("title", repr(win32gui.GetWindowText(h)), "class", win32gui.GetClassName(h))
        print("client(x,y,w,h)", geometry(h))
        print("window rect", win32gui.GetWindowRect(h))
        print("style", hex(win32gui.GetWindowLong(h, win32con.GWL_STYLE)))
        print("foreground", win32gui.GetForegroundWindow() == h)
        print("iconic", win32gui.IsIconic(h))
    print("screen", win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1))
