"""Capture the game's client area as a BGR ndarray (1280x720 expected)."""
import ctypes
import numpy as np
import win32gui, win32ui
import win32con
from win import find_window, geometry

PW_RENDERFULLCONTENT = 2

def grab_printwindow(hwnd):
    x, y, w, h = geometry(hwnd)
    hdc = win32gui.GetDC(hwnd)
    mfc = win32ui.CreateDCFromHandle(hdc)
    mem = mfc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfc, w, h)
    mem.SelectObject(bmp)
    # flags 1 = client only, 2 = render full content
    ok = ctypes.windll.user32.PrintWindow(hwnd, mem.GetSafeHdc(), 1 | PW_RENDERFULLCONTENT)
    data = bmp.GetBitmapBits(True)
    img = np.frombuffer(data, dtype=np.uint8).reshape(h, w, 4)[:, :, :3].copy()
    win32gui.DeleteObject(bmp.GetHandle())
    mem.DeleteDC(); mfc.DeleteDC(); win32gui.ReleaseDC(hwnd, hdc)
    return img, ok

def grab_mss(hwnd):
    import mss
    x, y, w, h = geometry(hwnd)
    with mss.mss() as s:
        return np.array(s.grab({"left": x, "top": y, "width": w, "height": h}))[:, :, :3]

def grab(hwnd=None):
    hwnd = hwnd or find_window()
    img, ok = grab_printwindow(hwnd)
    if not ok or img.mean() < 2:
        img = grab_mss(hwnd)
    return img

if __name__ == "__main__":
    import cv2, sys, time
    h = find_window()
    t = time.perf_counter()
    a, ok = grab_printwindow(h)
    t1 = time.perf_counter()
    print("printwindow ok", ok, a.shape, "mean", a.mean(), "ms", (t1 - t) * 1000)
    out = sys.argv[1] if len(sys.argv) > 1 else "cap.png"
    cv2.imencode(".png", a)[1].tofile(out)
