"""Foreground mouse input via SendInput. Unreal reads the real cursor, so
window-message input does not reach the game."""
import ctypes, time
from ctypes import wintypes
import win32gui, win32con, win32api
from win import geometry

user32 = ctypes.windll.user32

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]

class _U(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("pad", ctypes.c_byte * 32)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]

MOVE, DOWN, UP, ABS, VDESK = 0x0001, 0x0002, 0x0004, 0x8000, 0x4000

def _send(flags, x=0, y=0):
    i = INPUT(type=0)
    i.u.mi = MOUSEINPUT(x, y, 0, flags, 0, None)
    user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INPUT))

def _abs(sx, sy):
    vx, vy = [user32.GetSystemMetrics(n) for n in (76, 77)]
    vw, vh = [user32.GetSystemMetrics(n) for n in (78, 79)]
    return int((sx - vx) * 65535 / (vw - 1)), int((sy - vy) * 65535 / (vh - 1))

def move_screen(sx, sy):
    ax, ay = _abs(sx, sy)
    _send(MOVE | ABS | VDESK, ax, ay)

def focus(hwnd):
    """Bring the game forward; returns True when it is the foreground window."""
    if win32gui.GetForegroundWindow() == hwnd:
        return True
    # ALT tap lifts Windows' foreground lock for this process.
    win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
    win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(0.25)
    return win32gui.GetForegroundWindow() == hwnd

def _to_screen(hwnd, x, y):
    gx, gy, _, _ = geometry(hwnd)
    return gx + x, gy + y

def click(hwnd, x, y, hold=0.06):
    sx, sy = _to_screen(hwnd, x, y)
    move_screen(sx, sy); time.sleep(0.05)
    _send(DOWN); time.sleep(hold); _send(UP)

def drag(hwnd, x0, y0, x1, y1, steps=8, step_ms=12, hold=0.06):
    sx, sy = _to_screen(hwnd, x0, y0)
    ex, ey = _to_screen(hwnd, x1, y1)
    move_screen(sx, sy); time.sleep(0.05)
    _send(DOWN); time.sleep(hold)
    for i in range(1, steps + 1):
        move_screen(sx + (ex - sx) * i / steps, sy + (ey - sy) * i / steps)
        time.sleep(step_ms / 1000)
    time.sleep(hold)
    _send(UP)
