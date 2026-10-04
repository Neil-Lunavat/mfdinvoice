"""A picture of the app's own window, for Feedback. Taken on this PC, when the person ticks the
box, and shown to them before anything is sent.

The window and nothing else: Windows is asked to draw this one window into a bitmap (`PrintWindow`), so whatever else
is open on the screen - a bank, a chat - is never in it, even when it overlaps. Only if Windows draws nothing is the
window's own rectangle of the screen taken instead.
"""

from __future__ import annotations

import ctypes
import io
import logging
from ctypes import wintypes

from PIL import Image

log = logging.getLogger(__name__)

WIDEST = 1600                              # a wider window is scaled down: the picture is to read, not to print
_CLIENT_ONLY, _FULL_CONTENT = 0x1, 0x2     # PrintWindow: the inside of the window; what the GPU composed (a web view)


class _Header(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


def handle_of(window, title: str) -> int:
    """The window's handle: from the window itself, else by its title."""
    try:
        return int(window.native.Handle.ToInt64())
    except Exception:
        return int(ctypes.windll.user32.FindWindowW(None, title) or 0)


def window_png(hwnd: int) -> bytes:
    """The window as a PNG, or b"" when no picture could be taken."""
    if not hwnd:
        return b""
    try:
        im = _printed(hwnd)
        if im is None or _blank(im):
            im = _from_screen(hwnd)
        if im is None or _blank(im):
            return b""
        if im.width > WIDEST:
            im = im.resize((WIDEST, round(im.height * WIDEST / im.width)), Image.LANCZOS)
        out = io.BytesIO()
        im.save(out, "PNG", optimize=True)
        return out.getvalue()
    except Exception as e:                                # a picture is never worth an error
        log.info("no picture of the window: %s", e)
        return b""


def _size(hwnd: int) -> tuple[int, int]:
    rect = wintypes.RECT()
    ctypes.windll.user32.GetClientRect(wintypes.HWND(hwnd), ctypes.byref(rect))
    return rect.right - rect.left, rect.bottom - rect.top


def _printed(hwnd: int) -> Image.Image | None:
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    user32.GetDC.restype = gdi32.CreateCompatibleDC.restype = gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
    gdi32.SelectObject.restype = ctypes.c_void_p
    user32.GetDC.argtypes = [ctypes.c_void_p]
    user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    user32.PrintWindow.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
    gdi32.CreateCompatibleDC.argtypes = gdi32.DeleteDC.argtypes = gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
    gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT, wintypes.UINT, ctypes.c_void_p,
                                ctypes.c_void_p, wintypes.UINT]
    w, h = _size(hwnd)
    if w <= 0 or h <= 0:
        return None
    screen = user32.GetDC(hwnd)
    mem = gdi32.CreateCompatibleDC(screen)
    bitmap = gdi32.CreateCompatibleBitmap(screen, w, h)
    try:
        gdi32.SelectObject(mem, bitmap)
        if not user32.PrintWindow(hwnd, mem, _CLIENT_ONLY | _FULL_CONTENT):
            return None
        head = _Header(biSize=ctypes.sizeof(_Header), biWidth=w, biHeight=-h, biPlanes=1, biBitCount=32)
        pixels = ctypes.create_string_buffer(w * h * 4)
        if not gdi32.GetDIBits(mem, bitmap, 0, h, pixels, ctypes.byref(head), 0):
            return None
        return Image.frombuffer("RGB", (w, h), pixels.raw, "raw", "BGRX", 0, 1)
    finally:
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(hwnd, screen)


def _from_screen(hwnd: int) -> Image.Image | None:
    from PIL import ImageGrab
    w, h = _size(hwnd)
    corner = wintypes.POINT(0, 0)
    ctypes.windll.user32.ClientToScreen(wintypes.HWND(hwnd), ctypes.byref(corner))
    if w <= 0 or h <= 0:
        return None
    return ImageGrab.grab(bbox=(corner.x, corner.y, corner.x + w, corner.y + h)).convert("RGB")


def _blank(im: Image.Image) -> bool:
    """One flat colour: nothing was drawn."""
    return all(low == high for low, high in im.getextrema())
