# -*- coding: utf-8 -*-
"""
Sonide — Windows Multitasking Note Sidebar (WYSIWYG Markdown + Hero Timer + 2-Col Live Window Grid)
===================================================================================================
"""
import argparse
import atexit
import ctypes
import json
import math
import os
import random
import re
import signal
import sys
import time
from ctypes import wintypes
import tkinter as tk
from tkinter import font as tkfont

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(HERE, "config.json")
PID_FILE = os.path.join(HERE, ".sidebar.pid")

DEFAULT_CFG = {
    "mode": "docked",
    "monitor": "2",
    "width": 480,
    "header_height": 32,
    "font_size": 11,
    "file_path": "notes.md",
    "timer_minutes": 25,
}

if sys.platform != "win32":
    print("Ung dung chi chay tren Windows.")
    sys.exit(1)

user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
imm32 = ctypes.WinDLL("imm32", use_last_error=True)

HWND = wintypes.HWND
LONG_PTR = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LONG_PTR, HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]


class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.UINT),
        ("flags", wintypes.UINT),
        ("showCmd", wintypes.UINT),
        ("ptMinPosition", POINT),
        ("ptMaxPosition", POINT),
        ("rcNormalPosition", RECT),
    ]


class APPBARDATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", HWND),
                ("uCallbackMessage", wintypes.UINT), ("uEdge", wintypes.UINT),
                ("rc", RECT), ("lParam", wintypes.LPARAM)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]


class DWM_THUMBNAIL_PROPERTIES(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("dwFlags", wintypes.DWORD),
        ("rcDestination", RECT),
        ("rcSource", RECT),
        ("opacity", wintypes.BYTE),
        ("fVisible", wintypes.BOOL),
        ("fSourceClientAreaOnly", wintypes.BOOL),
    ]


MONITORENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, ctypes.c_void_p, ctypes.c_void_p,
                                     ctypes.POINTER(RECT), wintypes.LPARAM)

user32.GetAncestor.argtypes = [HWND, wintypes.UINT]
user32.GetAncestor.restype = HWND
user32.SetWindowPos.argtypes = [HWND, HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.SetWindowPos.restype = wintypes.BOOL
user32.SetWindowRgn.argtypes = [HWND, wintypes.HANDLE, wintypes.BOOL]
user32.SetWindowRgn.restype = ctypes.c_int
user32.GetWindowRect.argtypes = [HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetWindowPlacement.argtypes = [HWND, ctypes.POINTER(WINDOWPLACEMENT)]
user32.GetWindowPlacement.restype = wintypes.BOOL
user32.SetWindowPlacement.argtypes = [HWND, ctypes.POINTER(WINDOWPLACEMENT)]
user32.SetWindowPlacement.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = HWND
user32.SetForegroundWindow.argtypes = [HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.IsWindow.argtypes = [HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsIconic.argtypes = [HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.IsZoomed.argtypes = [HWND]
user32.IsZoomed.restype = wintypes.BOOL
user32.GetWindowTextW.argtypes = [HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindow.argtypes = [HWND, wintypes.UINT]
user32.GetWindow.restype = HWND
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = wintypes.SHORT
user32.PostMessageW.argtypes = [HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.RedrawWindow.argtypes = [HWND, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
user32.RedrawWindow.restype = wintypes.BOOL
user32.EnumDisplayMonitors.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                       MONITORENUMPROC, wintypes.LPARAM]
user32.EnumDisplayMonitors.restype = wintypes.BOOL
user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
user32.GetMonitorInfoW.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

GetWindowLongPtrW = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
GetWindowLongPtrW.argtypes = [HWND, ctypes.c_int]
GetWindowLongPtrW.restype = LONG_PTR

SetWindowLongPtrW = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
SetWindowLongPtrW.argtypes = [HWND, ctypes.c_int, LONG_PTR]
SetWindowLongPtrW.restype = LONG_PTR

user32.CallWindowProcW.argtypes = [LONG_PTR, HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.CallWindowProcW.restype = LONG_PTR

imm32.ImmGetContext.argtypes = [HWND]
imm32.ImmGetContext.restype = wintypes.HANDLE
imm32.ImmReleaseContext.argtypes = [HWND, wintypes.HANDLE]
imm32.ImmReleaseContext.restype = wintypes.BOOL
imm32.ImmGetCompositionStringW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD]
imm32.ImmGetCompositionStringW.restype = wintypes.LONG
imm32.ImmNotifyIME.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
imm32.ImmNotifyIME.restype = wintypes.BOOL

user32.SetLayeredWindowAttributes.argtypes = [
    HWND, wintypes.DWORD, wintypes.BYTE, wintypes.DWORD
]
user32.SetLayeredWindowAttributes.restype = wintypes.BOOL

shell32.SHAppBarMessage.argtypes = [wintypes.DWORD, ctypes.POINTER(APPBARDATA)]
shell32.SHAppBarMessage.restype = ctypes.c_size_t

kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
kernel32.TerminateProcess.restype = wintypes.BOOL
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD

dwmapi.DwmRegisterThumbnail.argtypes = [HWND, HWND, ctypes.POINTER(wintypes.HANDLE)]
dwmapi.DwmRegisterThumbnail.restype = ctypes.c_long
dwmapi.DwmUnregisterThumbnail.argtypes = [wintypes.HANDLE]
dwmapi.DwmUnregisterThumbnail.restype = ctypes.c_long
dwmapi.DwmUpdateThumbnailProperties.argtypes = [wintypes.HANDLE, ctypes.POINTER(DWM_THUMBNAIL_PROPERTIES)]
dwmapi.DwmUpdateThumbnailProperties.restype = ctypes.c_long
dwmapi.DwmQueryThumbnailSourceSize.argtypes = [wintypes.HANDLE, ctypes.POINTER(SIZE)]
dwmapi.DwmQueryThumbnailSourceSize.restype = ctypes.c_long

ABM_NEW, ABM_REMOVE, ABM_QUERYPOS, ABM_SETPOS = 0, 1, 2, 3
ABE_RIGHT = 2
WM_APPBAR = 0x0400 + 1
WM_CLOSE = 0x0010
GA_ROOT = 2
GW_OWNER = 4
GWLP_WNDPROC = -4
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
LWA_ALPHA = 0x00000002
WM_IME_SETCONTEXT = 0x0281
WM_IME_STARTCOMPOSITION = 0x010D
WM_IME_ENDCOMPOSITION = 0x010E
WM_IME_COMPOSITION = 0x010F
ISC_SHOWUICOMPOSITIONWINDOW = 0x80000000
GCS_COMPSTR = 0x0008
GCS_CURSORPOS = 0x0080
GCS_RESULTSTR = 0x0800
NI_COMPOSITIONSTR = 0x0015
CPS_COMPLETE = 0x0001
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_NOACTIVATE, SWP_FRAMECHANGED = 0x1, 0x2, 0x4, 0x10, 0x20
SWP_NOSENDCHANGING = 0x0400
SW_RESTORE, SW_MAXIMIZE, SW_SHOWNOACTIVATE, SW_MINIMIZE = 9, 3, 4, 6
HWND_TOPMOST = HWND(-1)
HWND_BOTTOM = HWND(1)
HWND_TOP = HWND(0)
VK_LBUTTON, VK_MENU, VK_Q, VK_W, VK_Z = 0x01, 0x12, 0x51, 0x57, 0x5A
RGN_DIFF = 4

RDW_INVALIDATE = 0x0001
RDW_ALLCHILDREN = 0x0080
RDW_FRAME = 0x0400

DWM_TNP_RECTDESTINATION = 0x00000001
DWM_TNP_OPACITY = 0x00000004
DWM_TNP_VISIBLE = 0x00000008
DWM_TNP_SOURCECLIENTAREAONLY = 0x00000010


def enable_dpi_awareness():
    for fn in (
        lambda: ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)),
        lambda: ctypes.windll.shcore.SetProcessDpiAwareness(2),
        lambda: user32.SetProcessDPIAware(),
    ):
        try:
            fn()
            return
        except Exception:
            pass


def atomic_write_text(path, text):
    """Write text atomically via temp file + fsync + os.replace to prevent 0-byte truncation on crash."""
    tmp_path = f"{path}.tmp.{os.getpid()}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def resolve_safe_note_path(raw_path):
    """Prevent path traversal outside workspace directory."""
    default_p = os.path.abspath(os.path.join(HERE, "notes.md"))
    if not raw_path or not isinstance(raw_path, str):
        return default_p
    try:
        cand = os.path.abspath(os.path.join(HERE, raw_path))
        if os.path.commonpath([HERE, cand]) == os.path.abspath(HERE) and cand.lower().endswith(".md"):
            return cand
    except Exception:
        pass
    return default_p


def stop_running_instance():
    if not os.path.isfile(PID_FILE):
        return False
    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        if not raw or raw.startswith("STOP"):
            return False
        parts = raw.split(":")
        old_pid = int(parts[0])
        old_hwnd = int(parts[1]) if len(parts) > 1 else 0
    except Exception:
        return False

    if old_pid == os.getpid():
        return False

    # Verify old_hwnd still exists and belongs to old_pid to prevent PID-reuse termination of unrelated apps
    if not old_hwnd or not user32.IsWindow(old_hwnd):
        try:
            os.remove(PID_FILE)
        except Exception:
            pass
        return False

    win_pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(old_hwnd, ctypes.byref(win_pid))
    if win_pid.value != old_pid:
        try:
            os.remove(PID_FILE)
        except Exception:
            pass
        return False

    PROCESS_TERMINATE = 0x0001
    SYNCHRONIZE = 0x00100000
    h_proc = kernel32.OpenProcess(PROCESS_TERMINATE | SYNCHRONIZE, False, old_pid)
    if not h_proc:
        try:
            os.remove(PID_FILE)
        except Exception:
            pass
        return False

    try:
        try:
            atomic_write_text(PID_FILE, f"STOP:{old_pid}")
        except Exception:
            pass
        user32.PostMessageW(old_hwnd, WM_CLOSE, 0, 0)
        res = kernel32.WaitForSingleObject(h_proc, 2000)
        if res != 0:
            kernel32.TerminateProcess(h_proc, 0)
            kernel32.WaitForSingleObject(h_proc, 1000)
    finally:
        kernel32.CloseHandle(h_proc)

    try:
        if os.path.isfile(PID_FILE):
            os.remove(PID_FILE)
    except Exception:
        pass
    return True


def acquire_single_instance(takeover=True):
    name = "Local\\SimpleNoteSidebar_Mutex"
    if takeover:
        stop_running_instance()
        time.sleep(0.25)

    m = kernel32.CreateMutexW(None, False, name)
    if kernel32.GetLastError() == 183:
        if takeover:
            if m:
                kernel32.CloseHandle(m)
            time.sleep(0.4)
            m = kernel32.CreateMutexW(None, False, name)
            if kernel32.GetLastError() == 183:
                if m:
                    kernel32.CloseHandle(m)
                return None
        else:
            if m:
                kernel32.CloseHandle(m)
            return None
    return m


def write_pid_file(hwnd_val=0):
    try:
        atomic_write_text(PID_FILE, f"{os.getpid()}:{int(hwnd_val or 0)}")
    except Exception:
        pass


def load_cfg():
    cfg = dict(DEFAULT_CFG)
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            if isinstance(loaded, dict):
                cfg.update(loaded)
    except FileNotFoundError:
        save_cfg(cfg)
    except Exception:
        pass
    return cfg


def save_cfg(cfg):
    try:
        atomic_write_text(CFG_PATH, json.dumps(cfg, indent=2, ensure_ascii=False))
    except Exception:
        pass


def list_monitors():
    mons = []

    def cb(hmon, hdc, lprc, lparam):
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
        r = mi.rcMonitor
        w = mi.rcWork
        mons.append({
            "rect": (r.left, r.top, r.right, r.bottom),
            "work": (w.left, w.top, w.right, w.bottom),
            "primary": bool(mi.dwFlags & 1),
        })
        return True

    cb_proc = MONITORENUMPROC(cb)
    user32.EnumDisplayMonitors(None, None, cb_proc, 0)
    mons.sort(key=lambda m: (m["rect"][0], m["rect"][1]))
    return mons


def pick_monitor(setting):
    mons = list_monitors()
    if not mons:
        return None
    if isinstance(setting, str):
        s = setting.strip().lower()
        if s in ("primary", "main"):
            return next((m for m in mons if m["primary"]), mons[0])
    if isinstance(setting, int) or (isinstance(setting, str) and setting.isdigit()):
        i = max(1, min(int(setting), len(mons)))
        return mons[i - 1]
    return next((m for m in mons if m["primary"]), mons[0])


def choose_monitor_cli(cfg):
    mons = list_monitors()
    if not mons or len(mons) == 1:
        cfg["monitor"] = "1"
        save_cfg(cfg)
        return

    cur_mon = pick_monitor(cfg.get("monitor", "2"))
    cur_idx = next((i for i, m in enumerate(mons, 1)
                    if m["rect"] == (cur_mon["rect"] if cur_mon else None)), 2)

    print("========================================")
    print("   SELECT MONITOR FOR SONIDE")
    print("========================================")
    for i, m in enumerate(mons, 1):
        l, t, r, b = m["rect"]
        is_pri = " [Chinh / Primary]" if m["primary"] else ""
        is_cur = "  <-- (Dang chon)" if i == cur_idx else ""
        print(f"  [{i}] Monitor {i}: {r - l}x{b - t} tai ({l},{t}){is_pri}{is_cur}")
    print("----------------------------------------")
    try:
        ans = input(f"Chon monitor (1-{len(mons)}) [Enter = Monitor {cur_idx}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        sys.exit(0)
    if ans.isdigit() and 1 <= int(ans) <= len(mons):
        cur_idx = int(ans)
    cfg["monitor"] = str(cur_idx)
    save_cfg(cfg)


def get_window_title(hwnd):
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value.strip()


def short_app_label(hwnd):
    full = get_window_title(hwnd)
    if not full:
        return "Window"
    parts = [p.strip() for p in re.split(r" [-–—|] ", full) if p.strip()]
    app_name = parts[-1] if len(parts) > 1 else parts[0]
    first_part = parts[0]
    label = app_name if len(app_name) <= 11 else first_part
    return label[:11] + ("…" if len(label) > 11 else "")


def get_window_rect(hwnd):
    rc = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rc))
    return (rc.left, rc.top, rc.right, rc.bottom)


def get_normal_window_rect(hwnd):
    wp = WINDOWPLACEMENT()
    wp.length = ctypes.sizeof(WINDOWPLACEMENT)
    if user32.GetWindowPlacement(hwnd, ctypes.byref(wp)):
        nr = wp.rcNormalPosition
        if nr.right > nr.left and nr.bottom > nr.top:
            return (nr.left, nr.top, nr.right, nr.bottom)
    return get_window_rect(hwnd)


# ----------------------------------------------------------------------------
# Anti-Aliased Rounded Green Checkbox Generator (Bo goc + Xanh la #22c55e)
# ----------------------------------------------------------------------------
def _lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def _sd_rounded_box(px, py, cx, cy, half_size, radius):
    dx = abs(px - cx) - (half_size - radius)
    dy = abs(py - cy) - (half_size - radius)
    out_dist = math.hypot(max(dx, 0.0), max(dy, 0.0))
    in_dist = min(max(dx, dy), 0.0)
    return out_dist + in_dist - radius


def _dist_to_segment(px, py, x1, y1, x2, y2):
    vx, vy = x2 - x1, y2 - y1
    wx, wy = px - x1, py - y1
    c1 = vx * wx + vy * wy
    if c1 <= 0:
        return math.hypot(px - x1, py - y1)
    c2 = vx * vx + vy * vy
    if c2 <= c1:
        return math.hypot(px - x2, py - y2)
    b = c1 / c2
    bx, by = x1 + b * vx, y1 + b * vy
    return math.hypot(px - bx, py - by)


def build_rounded_checkbox_images():
    size = 18
    cx, cy = 8.5, 9.0
    half_s = 6.8
    radius = 3.6

    bg = (0, 0, 0)
    unchecked_fill = (18, 18, 22)
    unchecked_border = (63, 63, 70)
    checked_fill = (34, 197, 94)      # #22c55e Emerald Green
    checked_border = (74, 222, 128)   # #4ade80 Light Green rim
    tick_color = (255, 255, 255)

    img_todo = tk.PhotoImage(width=size, height=size)
    img_done = tk.PhotoImage(width=size, height=size)

    rows_todo = []
    rows_done = []

    for y in range(size):
        row_t = []
        row_d = []
        for x in range(size):
            rt_acc = [0, 0, 0]
            rd_acc = [0, 0, 0]
            for sy in (-0.25, 0.25):
                for sx in (-0.25, 0.25):
                    px, py = x + sx, y + sy
                    d = _sd_rounded_box(px, py, cx, cy, half_s, radius)

                    if d > 0.6:
                        ct = bg
                    elif d > -1.1:
                        outer_a = 1.0 - max(0.0, (d + 0.2) / 0.8)
                        inner_a = max(0.0, (-d) / 1.1)
                        c_mid = _lerp_color(unchecked_border, unchecked_fill, inner_a)
                        ct = _lerp_color(bg, c_mid, outer_a)
                    else:
                        ct = unchecked_fill

                    if d > 0.6:
                        cd = bg
                    else:
                        outer_a = 1.0 - max(0.0, (d + 0.3) / 0.9)
                        base_g = _lerp_color(checked_border, checked_fill, min(1.0, max(0.0, -d / 1.2)))
                        cd = _lerp_color(bg, base_g, outer_a)

                        dt1 = _dist_to_segment(px, py, 5.1, 9.2, 7.6, 11.7)
                        dt2 = _dist_to_segment(px, py, 7.6, 11.7, 12.2, 6.4)
                        dt = min(dt1, dt2)
                        if dt < 1.35:
                            tick_a = 1.0 - max(0.0, (dt - 0.65) / 0.7)
                            cd = _lerp_color(cd, tick_color, tick_a)

                    for k in range(3):
                        rt_acc[k] += ct[k]
                        rd_acc[k] += cd[k]

            rt = tuple(v // 4 for v in rt_acc)
            rd = tuple(v // 4 for v in rd_acc)
            row_t.append(f"#{rt[0]:02x}{rt[1]:02x}{rt[2]:02x}")
            row_d.append(f"#{rd[0]:02x}{rd[1]:02x}{rd[2]:02x}")

        rows_todo.append("{" + " ".join(row_t) + "}")
        rows_done.append("{" + " ".join(row_d) + "}")

    img_todo.put(" ".join(rows_todo))
    img_done.put(" ".join(rows_done))
    return img_todo, img_done


# ----------------------------------------------------------------------------
# Markdown Parser & Serializer Engine
# ----------------------------------------------------------------------------
class MarkdownEngine:
    INLINE_RE = re.compile(
        r"(\*\*==(.+?)==\*\*|==\*\*(.+?)\*\*==|\*\*(.+?)\*\*|==(.+?)==|`([^`]+)`)"
    )

    @staticmethod
    def insert_checkbox(editor, index, checked, img_todo, img_done):
        img = img_done if checked else img_todo
        editor.image_create(index, image=img, padx=2, align="center")
        box_tag = "check_done_marker" if checked else "check_todo_marker"
        editor.insert(f"{index}+1c", " ", ("check_space", box_tag))

    @staticmethod
    def line_checkbox_state(editor, line_num):
        tags = set(editor.tag_names(f"{line_num}.0")) | set(editor.tag_names(f"{line_num}.1"))
        if "check_done_marker" in tags:
            return "done"
        if "check_todo_marker" in tags:
            return "todo"
        return None

    @staticmethod
    def load_to_text(editor, markdown_content, img_todo, img_done):
        editor.delete("1.0", "end")
        lines = markdown_content.split("\n")
        for i, line in enumerate(lines):
            if i > 0:
                editor.insert("end", "\n")

            if line.strip() == "---":
                editor.insert("end", "────────────────────────────────────────", ("hr",))
            elif line.startswith("### "):
                ln_idx = i + 1
                editor.insert("end", "\u200b", ("h3",))
                MarkdownEngine._insert_formatted(editor, line[4:], base_tag="h3")
                editor.insert("end", "\u200b", ("h3",))
                editor.tag_add("h3", f"{ln_idx}.0", f"{ln_idx}.end+1c")
            elif line.startswith("## "):
                ln_idx = i + 1
                editor.insert("end", "\u200b", ("h2",))
                MarkdownEngine._insert_formatted(editor, line[3:], base_tag="h2")
                editor.insert("end", "\u200b", ("h2",))
                editor.tag_add("h2", f"{ln_idx}.0", f"{ln_idx}.end+1c")
            elif line.startswith("# "):
                ln_idx = i + 1
                editor.insert("end", "\u200b", ("h1",))
                MarkdownEngine._insert_formatted(editor, line[2:], base_tag="h1")
                editor.insert("end", "\u200b", ("h1",))
                editor.tag_add("h1", f"{ln_idx}.0", f"{ln_idx}.end+1c")
            elif line.startswith("- [x] ") or line.startswith("- [X] "):
                line_start = editor.index("end-1c")
                MarkdownEngine.insert_checkbox(editor, line_start, True, img_todo, img_done)
                MarkdownEngine._insert_formatted(editor, line[6:], base_tag="check_done")
            elif line.startswith("- [ ] "):
                line_start = editor.index("end-1c")
                MarkdownEngine.insert_checkbox(editor, line_start, False, img_todo, img_done)
                MarkdownEngine._insert_formatted(editor, line[6:], base_tag="todo_line")
            elif line.startswith("- ") or line.startswith("* "):
                editor.insert("end", "• ", ("bullet_prefix", "bullet_line"))
                MarkdownEngine._insert_formatted(editor, line[2:], base_tag="bullet_line")
            elif line.startswith("> "):
                editor.insert("end", "▎ ", ("quote_bar", "quote_line"))
                MarkdownEngine._insert_formatted(editor, line[2:], base_tag="quote_line")
            else:
                MarkdownEngine._insert_formatted(editor, line)

    @staticmethod
    def _insert_formatted(editor, line, base_tag=None):
        last_idx = 0
        base = (base_tag,) if base_tag else ()
        for m in MarkdownEngine.INLINE_RE.finditer(line):
            start, end = m.span()
            if start > last_idx:
                editor.insert("end", line[last_idx:start], base)

            if m.group(2) is not None or m.group(3) is not None:
                content = m.group(2) if m.group(2) is not None else m.group(3)
                editor.insert("end", content, base + ("bold", "highlight"))
            elif m.group(4) is not None:
                editor.insert("end", m.group(4), base + ("bold",))
            elif m.group(5) is not None:
                editor.insert("end", m.group(5), base + ("highlight",))
            elif m.group(6) is not None:
                editor.insert("end", m.group(6), base + ("code",))
            last_idx = end

        if last_idx < len(line):
            editor.insert("end", line[last_idx:], base)

    @staticmethod
    def dump_from_text(editor):
        lines = []
        num_lines = int(editor.index("end-1c").split(".")[0])
        for line_num in range(1, num_lines + 1):
            lines.append(MarkdownEngine._dump_line(editor, line_num))
        return "\n".join(lines)

    @staticmethod
    def _dump_line(editor, line_num):
        start = f"{line_num}.0"
        end = f"{line_num}.end"
        raw_text = editor.get(start, end)
        tags_start = set(editor.tag_names(start)) | set(editor.tag_names(f"{line_num}.1"))

        if "hr" in tags_start and raw_text.replace("\u200b", "").strip("─").strip() == "":
            return "---"

        cb_state = MarkdownEngine.line_checkbox_state(editor, line_num)
        res = []
        tk_offset = 0
        str_start = 0

        if cb_state == "done":
            res.append("- [x] ")
            tk_offset = 1
            str_start = 1 if raw_text.startswith(" ") else 0
        elif cb_state == "todo":
            res.append("- [ ] ")
            tk_offset = 1
            str_start = 1 if raw_text.startswith(" ") else 0
        elif "h1" in tags_start:
            res.append("# ")
        elif "h2" in tags_start:
            res.append("## ")
        elif "h3" in tags_start:
            res.append("### ")
        elif raw_text.startswith("• "):
            res.append("- ")
            str_start = 2
        elif raw_text.startswith("▎ "):
            res.append("> ")
            str_start = 2

        body_clean = raw_text[str_start:].replace("\u200b", "")
        if not body_clean:
            return "".join(res).rstrip() if not cb_state else "".join(res)

        has_inline = (
            bool(editor.tag_nextrange("bold", start, end))
            or bool(editor.tag_nextrange("highlight", start, end))
            or bool(editor.tag_nextrange("code", start, end))
        )
        if not has_inline:
            res.append(body_clean)
            return "".join(res)

        cur_bold = False
        cur_hl = False
        cur_code = False
        buf = []

        def flush_buf():
            if not buf:
                return
            seg = "".join(buf)
            if cur_code:
                seg = f"`{seg}`"
            else:
                if cur_bold:
                    seg = f"**{seg}**"
                if cur_hl:
                    seg = f"=={seg}=="
            res.append(seg)
            buf.clear()

        for i in range(str_start, len(raw_text)):
            ch = raw_text[i]
            if ch == "\u200b":
                continue
            tk_col = i + tk_offset
            tags = set(editor.tag_names(f"{line_num}.{tk_col}"))
            bold = "bold" in tags
            hl = "highlight" in tags
            code = "code" in tags

            if (bold, hl, code) != (cur_bold, cur_hl, cur_code):
                flush_buf()
                cur_bold, cur_hl, cur_code = bold, hl, code
            buf.append(ch)

        flush_buf()
        return "".join(res)


# ----------------------------------------------------------------------------
# Main Application
# ----------------------------------------------------------------------------
class NoteSidebarApp:
    BG = "#000000"
    SURFACE = "#08080a"
    CARD_BG = "#0d0d11"
    BORDER = "#1c1c22"
    FG = "#f4f4f5"
    MUTED = "#71717a"
    DONE_FG = "#52525b"
    GREEN = "#22c55e"
    GREEN_DIM = "#14532d"
    SKY = "#38bdf8"
    VIOLET = "#a78bfa"
    AMBER = "#f59e0b"
    AMBER_BG = "#3b2306"
    AMBER_FG = "#fde68a"
    RED = "#ef4444"
    CODE_BG = "#18181b"
    CODE_FG = "#38bdf8"
    BTN_HOVER = "#1f1f26"

    def __init__(self, cfg):
        self.cfg = cfg
        self.mode = cfg.get("mode", "docked")
        self.width = max(340, min(1000, int(cfg.get("width", 480))))
        self.header_height = int(cfg.get("header_height", 32))
        self.base_font_size = 11
        self.font_size = max(8, min(24, int(cfg.get("font_size", 11))))
        self.file_path = resolve_safe_note_path(cfg.get("file_path", "notes.md"))
        self._last_checked_fg = None

        self.registered = False
        self.collapsed = False
        self.done = False
        self.save_timer = None
        self.mon_rect = None
        self.mon_work = None
        self.sidebar_rect = (0, 0, 0, 0)
        self.filter_todo_only = False

        # Tracking & Distributed Render Scheduler
        self.last_external_hwnd = None
        self._q_was_down = False
        self._w_was_down = False
        self._z_was_down = False
        self._lbutton_was_down = False
        self._drag_candidate_hwnd = None
        self._drag_candidate_start_rect = None
        self._drag_candidate_was_zoomed = False
        self._drag_is_moving = False
        self._drop_zone_active = False
        self._rr_render_idx = 0

        # Live Window Dock items (2-column grid)
        self.live_windows = {}
        self.thumb_height = 88

        # Timer state
        self.timer_default_sec = int(cfg.get("timer_minutes", 25)) * 60
        self.timer_remaining = self.timer_default_sec
        self.timer_total = self.timer_default_sec
        self.timer_running = False
        self.timer_job = None
        self._pulse_state = False

        self._drag_x = 0
        self._drag_y = 0
        self._resizing = False
        self._float_resize_right = 0

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.configure(bg=self.BG)
        self.root.attributes("-topmost", True)
        self._poll_tick_count = 0
        self._pill_dragging = False
        self._pill_drag_offset_y = 0

        # Motivation Quotes state
        self.motivation_collapsed = bool(cfg.get("motivation_collapsed", False))
        self._quotes_data = self._load_motivation_quotes()
        self._current_quote = None
        self._last_quote_idx = -1

        self.img_todo, self.img_done = build_rounded_checkbox_images()
        self._init_fonts()
        self.build_ui()

        self.root.geometry("200x200+0+0")
        self.root.update_idletasks()
        self.hwnd = user32.GetAncestor(self.root.winfo_id(), GA_ROOT)
        self._install_inline_ime()
        write_pid_file(self.hwnd)

        self.abd = APPBARDATA()
        self.abd.cbSize = ctypes.sizeof(APPBARDATA)
        self.abd.hWnd = self.hwnd
        self.abd.uCallbackMessage = WM_APPBAR

        self.load_notes()
        self.shuffle_motivation_quote()

        if self.mode == "floating":
            self.float_window()
        else:
            self.dock_sidebar()

        atexit.register(self.cleanup)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.after(42, self.poll_multitask)
        self.root.after(42, self._distributed_render_tick)

    def _init_fonts(self):
        sz = self.font_size
        self.f_normal = tkfont.Font(family="Segoe UI", size=sz)
        self.f_bold = tkfont.Font(family="Segoe UI", size=sz, weight="bold")
        self.f_italic = tkfont.Font(family="Segoe UI", size=sz, slant="italic")
        self.f_strike = tkfont.Font(family="Segoe UI", size=sz, overstrike=True)
        self.f_code = tkfont.Font(family="Consolas", size=max(9, sz - 1))
        self.f_h1 = tkfont.Font(family="Segoe UI", size=sz + 5, weight="bold")
        self.f_h2 = tkfont.Font(family="Segoe UI", size=sz + 3, weight="bold")
        self.f_h3 = tkfont.Font(family="Segoe UI", size=sz + 1, weight="bold")

    def _apply_font_zoom(self, new_size):
        self.font_size = max(8, min(24, int(new_size)))
        sz = self.font_size
        self.f_normal.configure(size=sz)
        self.f_bold.configure(size=sz)
        self.f_italic.configure(size=sz)
        self.f_strike.configure(size=sz)
        self.f_code.configure(size=max(9, sz - 1))
        self.f_h1.configure(size=sz + 5)
        self.f_h2.configure(size=sz + 3)
        self.f_h3.configure(size=sz + 1)

        pct = int(round((sz / self.base_font_size) * 100))
        self.zoom_lbl.config(text=f"{pct}%")
        self.cfg["font_size"] = sz
        save_cfg(self.cfg)

    def on_editor_zoom_wheel(self, event):
        delta = 1 if event.delta > 0 else -1
        self._apply_font_zoom(self.font_size + delta)
        return "break"

    # ------------------------------------------------------------------------
    # Sleek UI Construction
    # ------------------------------------------------------------------------
    def build_ui(self):
        # 0. Floating Mini Pill when collapsed (docked low on right edge to avoid covering tabs)
        self.mini_pill = tk.Frame(
            self.root,
            bg="#09090d",
            highlightbackground=self.GREEN,
            highlightthickness=1,
            cursor="hand2",
        )
        self.mini_pill_lbl = tk.Label(
            self.mini_pill,
            text="◀ SONIDE",
            bg="#09090d",
            fg=self.GREEN,
            font=("Segoe UI", 8, "bold"),
            cursor="hand2",
            padx=8,
            pady=4,
        )
        self.mini_pill_lbl.pack(fill="both", expand=True)
        for w in (self.mini_pill, self.mini_pill_lbl):
            w.bind("<ButtonPress-1>", self._on_pill_press)
            w.bind("<B1-Motion>", self._on_pill_drag)
            w.bind("<ButtonRelease-1>", self._on_pill_release)

        # Left Resize Grip (4px)
        self.resize_grip = tk.Frame(self.root, bg="#0c0c10", width=4, cursor="sb_h_double_arrow")
        self.resize_grip.pack(side="left", fill="y")
        self.resize_grip.bind("<ButtonPress-1>", self._start_resize)
        self.resize_grip.bind("<B1-Motion>", self._do_resize)
        self.resize_grip.bind("<ButtonRelease-1>", self._end_resize)
        self.resize_grip.bind("<Enter>", lambda e: self.resize_grip.config(bg=self.GREEN))
        self.resize_grip.bind("<Leave>", lambda e: self.resize_grip.config(bg="#0c0c10"))

        self.main_col = tk.Frame(self.root, bg=self.BG)
        self.main_col.pack(side="right", fill="both", expand=True)

        # 1. Minimalist Header Bar
        self.bar = tk.Frame(self.main_col, bg=self.SURFACE, height=self.header_height)
        self.bar.pack(side="top", fill="x")
        self.bar.pack_propagate(False)
        self.bar.bind("<Button-1>", self.start_drag)
        self.bar.bind("<B1-Motion>", self.do_drag)

        tk.Label(self.bar, text="  ●", bg=self.SURFACE, fg=self.GREEN,
                 font=("Segoe UI", 8, "bold")).pack(side="left")

        self.title_lbl = tk.Label(self.bar, text=" SONIDE", bg=self.SURFACE, fg="#e4e4e7",
                                  font=("Segoe UI", 8, "bold"), cursor="hand2")
        self.title_lbl.pack(side="left")
        self.title_lbl.bind("<Button-1>", self.start_drag)
        self.title_lbl.bind("<B1-Motion>", self.do_drag)

        self.status_lbl = tk.Label(self.bar, text=" · Saved", bg=self.SURFACE, fg="#52525b",
                                   font=("Segoe UI", 8))
        self.status_lbl.pack(side="left")

        def hdr_btn(text, cmd, fg_col=self.MUTED, w=3):
            b = tk.Label(self.bar, text=text, bg=self.SURFACE, fg=fg_col, width=w,
                         font=("Segoe UI", 9, "bold"), cursor="hand2")
            b.pack(side="right", fill="y")
            b.bind("<Button-1>", lambda e: cmd())
            b.bind("<Enter>", lambda e: b.config(bg=self.BTN_HOVER, fg="#ffffff"))
            b.bind("<Leave>", lambda e: b.config(bg=self.SURFACE, fg=fg_col))
            return b

        hdr_btn("✕", self.quit, fg_col="#a1a1aa", w=3)
        self.pin_btn = hdr_btn("📌" if self.mode == "docked" else "🗖", self.toggle_mode, w=3)
        self.mon_btn = hdr_btn("⇄", self.next_monitor, w=3)

        self.collapse_btn = tk.Label(
            self.bar,
            text="Hide »",
            bg="#121217",
            fg=self.GREEN,
            padx=8,
            font=("Segoe UI", 8, "bold"),
            cursor="hand2",
        )
        self.collapse_btn.pack(side="right", fill="y", padx=3, pady=4)
        self.collapse_btn.bind("<Button-1>", lambda e: self.toggle_collapse())
        self.collapse_btn.bind("<Enter>", lambda e: self.collapse_btn.config(bg="#1f2937", fg="#ffffff"))
        self.collapse_btn.bind("<Leave>", lambda e: self.collapse_btn.config(bg="#121217", fg=self.GREEN))

        # 2. Hero Focus Timer Card
        self.timer_card = tk.Frame(
            self.main_col,
            bg=self.CARD_BG,
            highlightbackground=self.BORDER,
            highlightthickness=1,
            padx=14,
            pady=8,
        )
        self.timer_card.pack(side="top", fill="x", padx=10, pady=(6, 4))

        t_row = tk.Frame(self.timer_card, bg=self.CARD_BG)
        t_row.pack(side="top", fill="x")

        self.time_lbl = tk.Label(
            t_row,
            text=self._fmt_sec(self.timer_remaining),
            bg=self.CARD_BG,
            fg="#ffffff",
            font=("Consolas", 25, "bold"),
            cursor="hand2",
        )
        self.time_lbl.pack(side="left")
        self.time_lbl.bind("<Button-1>", lambda e: self.toggle_timer())
        self.time_lbl.bind("<MouseWheel>", self._on_timer_wheel)

        t_ctrl = tk.Frame(t_row, bg=self.CARD_BG)
        t_ctrl.pack(side="right")

        t_ctrl_top = tk.Frame(t_ctrl, bg=self.CARD_BG)
        t_ctrl_top.pack(side="top", anchor="e")

        self.play_btn = tk.Label(
            t_ctrl_top,
            text="▶ Start",
            bg="#15803d",
            fg="#ffffff",
            padx=10,
            pady=2,
            font=("Segoe UI", 8, "bold"),
            cursor="hand2",
        )
        self.play_btn.pack(side="left", padx=(0, 4))
        self.play_btn.bind("<Button-1>", lambda e: self.toggle_timer())

        rst_btn = tk.Label(
            t_ctrl_top,
            text="↺",
            bg="#1f1f26",
            fg="#a1a1aa",
            padx=7,
            pady=2,
            font=("Segoe UI", 8, "bold"),
            cursor="hand2",
        )
        rst_btn.pack(side="left")
        rst_btn.bind("<Button-1>", lambda e: self.reset_timer())

        t_ctrl_bot = tk.Frame(t_ctrl, bg=self.CARD_BG)
        t_ctrl_bot.pack(side="bottom", anchor="e", pady=(4, 0))

        self.preset_btns = {}
        for mins in (15, 25, 45):
            is_cur = (mins * 60 == self.timer_total)
            b = tk.Label(
                t_ctrl_bot,
                text=f"{mins}m",
                bg="#1f2937" if is_cur else "#141419",
                fg=self.GREEN if is_cur else "#71717a",
                padx=7,
                pady=1,
                font=("Segoe UI", 8, "bold"),
                cursor="hand2",
            )
            b.pack(side="left", padx=(3, 0))
            b.bind("<Button-1>", lambda e, m=mins: self.set_timer_minutes(m))
            self.preset_btns[mins] = b

        self.progress_bg = tk.Canvas(self.timer_card, bg="#1c1c24", height=5,
                                     highlightthickness=0, bd=0)
        self.progress_bg.pack(side="bottom", fill="x", pady=(7, 0))
        self.progress_bar = self.progress_bg.create_rectangle(0, 0, 0, 5, fill=self.GREEN, width=0)

        # 2.5 Minimalist Motivation Card (Aesthetic, Centered, Large Georgia Font)
        self.motivation_card = tk.Frame(
            self.main_col,
            bg=self.CARD_BG,
            highlightbackground=self.BORDER,
            highlightthickness=1,
            padx=14,
            pady=10,
            cursor="hand2",
        )
        self.motivation_card.pack(side="top", fill="x", padx=10, pady=(2, 4))
        self.motivation_card.bind("<Button-1>", lambda e: self.shuffle_motivation_quote())

        self.quote_lbl = tk.Label(
            self.motivation_card,
            text="",
            bg=self.CARD_BG,
            fg="#ffffff",
            font=("Georgia", 13, "italic"),
            justify="center",
            anchor="center",
            cursor="hand2",
            wraplength=max(240, self.width - 56),
        )
        self.quote_lbl.pack(side="top", fill="x", pady=(2, 6))
        self.quote_lbl.bind("<Button-1>", lambda e: self.shuffle_motivation_quote())

        mot_bot = tk.Frame(self.motivation_card, bg=self.CARD_BG, cursor="hand2")
        mot_bot.pack(side="top", fill="x")
        mot_bot.bind("<Button-1>", lambda e: self.shuffle_motivation_quote())

        self.mot_note_btn = tk.Label(
            mot_bot,
            text="+ Note",
            bg=self.CARD_BG,
            fg="#52525b",
            font=("Segoe UI", 7, "bold"),
            cursor="hand2",
        )
        self.mot_note_btn.pack(side="left", padx=(2, 0))
        self.mot_note_btn.bind("<Button-1>", lambda e: self.insert_motivation_to_notes())
        self.mot_note_btn.bind("<Enter>", lambda e: self.mot_note_btn.config(fg=self.GREEN))
        self.mot_note_btn.bind("<Leave>", lambda e: self.mot_note_btn.config(fg="#52525b"))

        self.author_lbl = tk.Label(
            mot_bot,
            text="",
            bg=self.CARD_BG,
            fg="#a1a1aa",
            font=("Georgia", 9, "italic"),
            justify="right",
            anchor="e",
            cursor="hand2",
        )
        self.author_lbl.pack(side="right", padx=(0, 6))
        self.author_lbl.bind("<Button-1>", lambda e: self.shuffle_motivation_quote())

        # 3. Compact 2-Column Live Window Grid
        self.dock_panel = tk.Frame(self.main_col, bg=self.BG, padx=10, pady=2)
        self.dock_panel.pack(side="top", fill="x")

        self.dock_hdr = tk.Frame(self.dock_panel, bg=self.BG)
        self.dock_hdr.pack(side="top", fill="x")

        self.dock_title = tk.Label(
            self.dock_hdr,
            text="WINDOWS",
            bg=self.BG,
            fg="#71717a",
            font=("Segoe UI", 7, "bold"),
        )
        self.dock_title.pack(side="left")

        self.stash_btn = tk.Label(
            self.dock_hdr,
            text="+ Pin",
            bg="#111116",
            fg=self.GREEN,
            padx=7,
            pady=1,
            font=("Segoe UI", 8, "bold"),
            cursor="hand2",
        )
        self.stash_btn.pack(side="right")
        self.stash_btn.bind("<Button-1>", lambda e: self.stash_last_active_window())
        self.stash_btn.bind("<Enter>", lambda e: self.stash_btn.config(bg="#1c1c24"))
        self.stash_btn.bind("<Leave>", lambda e: self.stash_btn.config(bg="#111116"))

        self.dock_grid = tk.Frame(self.dock_panel, bg=self.BG, height=1)
        self.dock_grid.grid_columnconfigure(0, weight=1, uniform="live_col")
        self.dock_grid.grid_columnconfigure(1, weight=1, uniform="live_col")

        # 4. Sleek Toolbar
        self.nav_bar = tk.Frame(self.main_col, bg="#060608", padx=10, pady=4)
        self.nav_bar.pack(side="top", fill="x")

        def nav_pill(txt, cmd, fg_c="#a1a1aa"):
            b = tk.Label(self.nav_bar, text=txt, bg="#101014", fg=fg_c, padx=8, pady=2,
                         font=("Segoe UI", 8, "bold"), cursor="hand2")
            b.pack(side="left", padx=(0, 5))
            b.bind("<Button-1>", lambda e: cmd(e))
            b.bind("<Enter>", lambda e: b.config(bg="#1c1c24", fg="#ffffff"))
            b.bind("<Leave>", lambda e: b.config(bg="#101014", fg=fg_c))
            return b

        self.outline_btn = nav_pill("≡ Outline", self.show_outline_menu, fg_c=self.SKY)
        self.filter_btn = nav_pill("○ Pending", lambda e: self.toggle_todo_filter(), fg_c=self.GREEN)
        nav_pill("✓ Archive", lambda e: self.collect_done_tasks())

        pct = int(round((self.font_size / self.base_font_size) * 100))
        self.zoom_lbl = tk.Label(
            self.nav_bar,
            text=f"{pct}%",
            bg="#101014",
            fg="#71717a",
            padx=5,
            pady=1,
            font=("Consolas", 8, "bold"),
            cursor="hand2",
        )
        self.zoom_lbl.pack(side="right", padx=(4, 0))
        self.zoom_lbl.bind("<Button-1>", lambda e: self._apply_font_zoom(self.base_font_size))
        self.zoom_lbl.bind("<MouseWheel>", self.on_editor_zoom_wheel)

        self.task_stat_lbl = tk.Label(self.nav_bar, text="", bg="#060608", fg=self.MUTED,
                                      font=("Consolas", 8, "bold"))
        self.task_stat_lbl.pack(side="right")

        tk.Frame(self.main_col, bg="#141418", height=1).pack(side="top", fill="x")

        # 5. Markdown Editor
        self.editor = tk.Text(
            self.main_col,
            bg=self.BG,
            fg=self.FG,
            insertbackground=self.GREEN,
            insertwidth=2,
            selectbackground="#1f2937",
            selectforeground="#ffffff",
            font=self.f_normal,
            wrap="word",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=18,
            pady=14,
            spacing1=4,
            spacing2=5,
            spacing3=4,
            undo=True,
        )
        self.editor.pack(side="bottom", fill="both", expand=True)

        self.editor.tag_configure("h1", font=self.f_h1, foreground="#ffffff", spacing1=10, spacing3=5)
        self.editor.tag_configure("h2", font=self.f_h2, foreground=self.SKY, spacing1=8, spacing3=4)
        self.editor.tag_configure("h3", font=self.f_h3, foreground=self.VIOLET, spacing1=6, spacing3=3)
        self.editor.tag_configure("bold", font=self.f_bold, foreground="#ffffff")
        self.editor.tag_configure("highlight", background=self.AMBER_BG, foreground=self.AMBER_FG, font=self.f_bold)
        self.editor.tag_configure("code", background=self.CODE_BG, foreground=self.CODE_FG, font=self.f_code)
        self.editor.tag_configure("check_done", font=self.f_strike, foreground=self.DONE_FG, lmargin2=24)
        self.editor.tag_configure("todo_line", foreground=self.FG, lmargin2=24)
        self.editor.tag_configure("bullet_prefix", foreground=self.GREEN, font=self.f_bold)
        self.editor.tag_configure("bullet_line", foreground=self.FG, lmargin2=18)
        self.editor.tag_configure("quote_bar", foreground=self.GREEN, font=self.f_bold)
        self.editor.tag_configure("quote_line", foreground="#a1a1aa", font=self.f_italic, lmargin2=16)
        self.editor.tag_configure("hr", foreground="#27272a", spacing1=6, spacing3=6)
        self.editor.tag_configure("elided_done", elide=True)

        self.editor.bind("<KeyRelease>", self.on_key_release)
        self.editor.bind("<space>", self.on_space_autoformat)
        self.editor.bind("<Return>", self.on_enter)
        self.editor.bind("<BackSpace>", self.on_backspace)
        self.editor.bind("<Button-1>", self.on_editor_click)
        self.editor.bind("<Escape>", self.return_to_previous_window)
        self.editor.bind("<Control-MouseWheel>", self.on_editor_zoom_wheel)
        self.editor.bind("<Control-equal>", lambda e: self._apply_font_zoom(self.font_size + 1))
        self.editor.bind("<Control-minus>", lambda e: self._apply_font_zoom(self.font_size - 1))
        self.editor.bind("<Control-0>", lambda e: self._apply_font_zoom(self.base_font_size))

        self.editor.bind("<Control-b>", self.shortcut_bold)
        self.editor.bind("<Control-B>", self.shortcut_bold)
        self.editor.bind("<Control-h>", self.shortcut_highlight)
        self.editor.bind("<Control-H>", self.shortcut_highlight)
        self.editor.bind("<Control-e>", self.shortcut_code)
        self.editor.bind("<Control-E>", self.shortcut_code)
        self.editor.bind("<Control-d>", self.shortcut_checkbox)
        self.editor.bind("<Control-D>", self.shortcut_checkbox)
        self.editor.bind("<Control-s>", lambda e: self.save_notes(instant=True))
        self.editor.bind("<Control-S>", lambda e: self.save_notes(instant=True))

    # ------------------------------------------------------------------------
    # Hero Focus Timer Logic
    # ------------------------------------------------------------------------
    def _fmt_sec(self, sec):
        m, s = divmod(max(0, int(sec)), 60)
        return f"{m:02d}:{s:02d}"

    def set_timer_minutes(self, mins):
        self.timer_running_stop()
        self.timer_total = int(mins) * 60
        self.timer_remaining = self.timer_total
        self.cfg["timer_minutes"] = int(mins)
        save_cfg(self.cfg)
        for m, b in self.preset_btns.items():
            is_cur = (m == mins)
            b.config(bg="#1f2937" if is_cur else "#141419", fg=self.GREEN if is_cur else "#71717a")
        self._update_timer_ui()

    def _on_timer_wheel(self, event):
        delta_min = 1 if event.delta > 0 else -1
        new_sec = max(60, min(180 * 60, self.timer_remaining + delta_min * 60))
        self.timer_remaining = new_sec
        self.timer_total = max(self.timer_total, new_sec)
        self._update_timer_ui()

    def toggle_timer(self):
        if self.timer_running:
            self.timer_running_stop()
        else:
            if self.timer_remaining <= 0:
                self.timer_remaining = self.timer_total
            self.timer_running = True
            self.play_btn.config(text="⏸ Pause", bg="#b45309", fg="#ffffff")
            self._tick_timer()
        self._update_timer_ui()

    def timer_running_stop(self):
        self.timer_running = False
        if self.timer_job:
            self.root.after_cancel(self.timer_job)
            self.timer_job = None
        self.play_btn.config(text="▶ Start", bg="#15803d", fg="#ffffff")
        self.timer_card.config(highlightbackground=self.BORDER)

    def reset_timer(self):
        self.timer_running_stop()
        self.timer_remaining = self.timer_total
        self._update_timer_ui()

    def _tick_timer(self):
        if not self.timer_running:
            return
        if self.timer_remaining > 0:
            self.timer_remaining -= 1
            self._pulse_state = not self._pulse_state
            self._update_timer_ui()
            self.timer_job = self.root.after(1000, self._tick_timer)
        else:
            self.timer_running_stop()
            self.time_lbl.config(fg=self.RED, text="00:00!")
            self.timer_card.config(highlightbackground=self.RED)
            self.shuffle_motivation_quote()

    def _update_timer_ui(self):
        rem = self.timer_remaining
        if not self.timer_running:
            col = "#ffffff"
            border_col = self.BORDER
        elif rem <= 60:
            col = self.RED if self._pulse_state else "#fca5a5"
            border_col = self.RED
        elif rem <= 300:
            col = self.AMBER
            border_col = self.AMBER
        else:
            col = self.GREEN
            border_col = "#14532d"

        self.time_lbl.config(text=self._fmt_sec(rem), fg=col)
        self.timer_card.config(highlightbackground=border_col)

        w = max(1, self.progress_bg.winfo_width())
        ratio = 0.0 if self.timer_total <= 0 else (self.timer_total - rem) / self.timer_total
        self.progress_bg.coords(self.progress_bar, 0, 0, int(w * ratio), 5)
        self.progress_bg.itemconfig(self.progress_bar, fill=col if self.timer_running else self.GREEN)

    # ------------------------------------------------------------------------
    # Minimalist Motivation Card Logic
    # ------------------------------------------------------------------------
    def _load_motivation_quotes(self):
        qpath = os.path.join(HERE, "motivation_quotes.json")
        if os.path.isfile(qpath):
            try:
                with open(qpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and data:
                        return data
            except Exception:
                pass
        return [
            {"quote": "Focus is a muscle. You build it by not giving in to distractions.", "author": "Cal Newport"},
            {"quote": "Do one thing deeply rather than ten things superficially.", "author": "Marcus Aurelius"},
            {"quote": "Simplicity is prerequisite for reliability.", "author": "Edsger W. Dijkstra"},
            {"quote": "Your mind is for having ideas, not holding them.", "author": "David Allen"},
            {"quote": "Action is the foundational key to all success.", "author": "Pablo Picasso"},
        ]

    def shuffle_motivation_quote(self):
        if not self._quotes_data:
            return
        if len(self._quotes_data) == 1:
            idx = 0
        else:
            candidates = [i for i in range(len(self._quotes_data)) if i != self._last_quote_idx]
            idx = random.choice(candidates) if candidates else 0
        self._last_quote_idx = idx
        self._current_quote = self._quotes_data[idx]
        q = self._current_quote.get("quote", "")
        a = self._current_quote.get("author", "")
        if hasattr(self, "quote_lbl"):
            self.quote_lbl.config(text=f'“{q}”')
        if hasattr(self, "author_lbl"):
            self.author_lbl.config(text=f"— {a}")

    def toggle_motivation_collapse(self):
        pass

    def insert_motivation_to_notes(self):
        if not hasattr(self, "_current_quote") or not self._current_quote:
            return
        q = self._current_quote.get("quote", "")
        a = self._current_quote.get("author", "")
        if not q:
            return
        cursor = self.editor.index("insert")
        line_num, col = cursor.split(".")
        line_text = self.editor.get(f"{line_num}.0", f"{line_num}.end").replace("\u200b", "").strip()
        prefix = "\n\n" if line_text else ""
        txt = f'{prefix}> "{q}"\n> — *{a}*\n\n'
        self.editor.insert("insert", txt, ("quote_bar", "quote_line"))
        self.editor.see("insert")
        self.save_notes(instant=True)
        if hasattr(self, "mot_note_btn"):
            self.mot_note_btn.config(text="✓ Added", fg=self.GREEN)
            self.root.after(1200, lambda: self.mot_note_btn.config(text="+ Note", fg="#52525b"))

    def _update_motivation_wraplength(self):
        if hasattr(self, "quote_lbl"):
            w = max(240, self.root.winfo_width() - 56)
            self.quote_lbl.config(wraplength=w)

    # ------------------------------------------------------------------------
    # Anti-Occlusion Staggered Positioning & Persistent Live Window Dock
    # ------------------------------------------------------------------------
    def _is_valid_external_window(self, hwnd):
        if not hwnd or hwnd == self.hwnd or not user32.IsWindow(hwnd):
            return False
        if not user32.IsWindowVisible(hwnd):
            return False
        if user32.GetWindow(hwnd, GW_OWNER):
            return False
        ex = GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        if ex & WS_EX_TOOLWINDOW:
            return False
        title = get_window_title(hwnd)
        if not title or title in ("Program Manager", "Default IME", "MSCTFIME UI", "Windows Input Experience"):
            return False
        return True

    def _ensure_anti_occlusion_on_window(self, hwnd):
        if not hwnd or not user32.IsWindow(hwnd):
            return
        if not hasattr(self, "_layered_hwnds"):
            self._layered_hwnds = set()
        if hwnd in self._layered_hwnds:
            return
        try:
            ex = GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
            if not (ex & WS_EX_LAYERED):
                SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex | WS_EX_LAYERED)
                user32.SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA)
                self._layered_hwnds.add(hwnd)
        except Exception:
            pass

    def _cleanup_layered_hwnds(self):
        for h in list(getattr(self, "_layered_hwnds", set())):
            try:
                if user32.IsWindow(h):
                    ex = GetWindowLongPtrW(h, GWL_EXSTYLE)
                    if ex & WS_EX_LAYERED:
                        SetWindowLongPtrW(h, GWL_EXSTYLE, ex & ~WS_EX_LAYERED)
            except Exception:
                pass
        if hasattr(self, "_layered_hwnds"):
            self._layered_hwnds.clear()

    def _update_card_visuals(self, hwnd, pulse_target=None):
        info = self.live_windows.get(hwnd)
        if not info:
            return
        is_minimized = bool(user32.IsIconic(hwnd))
        is_front = bool(info.get("in_front", False)) and not is_minimized
        try:
            info["card"].config(
                highlightbackground=self.GREEN if is_front else "#272730"
            )
            act_lbl = info.get("act_lbl")
            if act_lbl:
                act_lbl.config(
                    text="↓ Back" if is_front else "↑ Top",
                    fg=self.AMBER if is_front else self.GREEN,
                    bg="#271a0c" if is_front else "#14141c",
                )
            dot = info.get("dot_lbl")
            if dot:
                dot.config(
                    fg=self.GREEN if is_front else (
                        "#4ade80" if hwnd == pulse_target else "#166534"
                    )
                )
        except Exception:
            pass

    def _distributed_render_tick(self):
        """
        24fps Paced Render Scheduler (~42ms tick):
        - Throttles background window refresh & DWM thumbnail updates to ~24fps to save resources.
        - Never restores minimized windows (native '-' Minimize button works 100% normally).
        """
        if self.done:
            return
        try:
            hwnds = list(self.live_windows.keys())
            if hwnds and not self.collapsed:
                if not hasattr(self, "_render_frame_counter"):
                    self._render_frame_counter = 0
                self._render_frame_counter += 1

                # Every ~12 frames (~500ms at 24fps), cycle card status & gentle redraw
                if self._render_frame_counter % 12 == 0:
                    self._rr_render_idx = self._rr_render_idx % len(hwnds)
                    target_hwnd = hwnds[self._rr_render_idx]
                    self._rr_render_idx = (self._rr_render_idx + 1) % len(hwnds)

                    fg = user32.GetForegroundWindow()
                    if self._is_valid_external_window(fg):
                        self._ensure_anti_occlusion_on_window(fg)

                    # Prune closed HWNDs from _layered_hwnds set
                    if hasattr(self, "_layered_hwnds") and self._layered_hwnds:
                        self._layered_hwnds = {h for h in self._layered_hwnds if user32.IsWindow(h)}

                    for h, info in list(self.live_windows.items()):
                        if not user32.IsWindow(h):
                            self.remove_live_window(h, restore=False)
                            continue
                        self._update_card_visuals(h, pulse_target=target_hwnd)

                    if (
                        user32.IsWindow(target_hwnd)
                        and target_hwnd in self.live_windows
                        and not user32.IsIconic(target_hwnd)
                    ):
                        user32.RedrawWindow(
                            target_hwnd, None, None, RDW_INVALIDATE | RDW_FRAME
                        )

                    self._refresh_dwm_thumbnails(query_source=True)
                else:
                    self._refresh_dwm_thumbnails(query_source=False)
        except Exception:
            pass
        # 42ms = ~24fps
        self.root.after(42, self._distributed_render_tick)

    def _restagger_stashed_windows(self):
        pass

    def _push_window_down(self, hwnd):
        """Push window to bottom Z-Order (HWND_BOTTOM) without moving or resizing."""
        info = self.live_windows.get(hwnd)
        if not info or not user32.IsWindow(hwnd):
            return
        info["in_front"] = False

        if user32.GetForegroundWindow() == hwnd:
            next_hwnd = None
            if (
                self.last_external_hwnd
                and self.last_external_hwnd != hwnd
                and user32.IsWindow(self.last_external_hwnd)
                and not user32.IsIconic(self.last_external_hwnd)
            ):
                next_hwnd = self.last_external_hwnd
            else:
                for h_other, other_info in self.live_windows.items():
                    if h_other != hwnd and user32.IsWindow(h_other) and not user32.IsIconic(h_other):
                        next_hwnd = h_other
                        break
            if next_hwnd:
                user32.SetForegroundWindow(next_hwnd)
                self._ensure_anti_occlusion_on_window(next_hwnd)
            else:
                user32.SetForegroundWindow(self.hwnd)

        user32.SetWindowPos(
            hwnd,
            HWND_BOTTOM,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        )
        if not self.collapsed and self.hwnd and user32.IsWindow(self.hwnd):
            user32.SetWindowPos(
                self.hwnd,
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
            )
        self._update_card_visuals(hwnd)

    def _bring_window_up(self, hwnd):
        """Bring window to top Z-Order (HWND_TOP) and restore if minimized."""
        info = self.live_windows.get(hwnd)
        if not info or not user32.IsWindow(hwnd):
            return

        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)

        self._ensure_anti_occlusion_on_window(hwnd)
        user32.SetWindowPos(
            hwnd,
            HWND_TOP,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE,
        )
        user32.SetForegroundWindow(hwnd)

        for h_other, other_info in self.live_windows.items():
            other_info["in_front"] = (h_other == hwnd)
            self._update_card_visuals(h_other)

        self.last_external_hwnd = hwnd
        if not self.collapsed and self.hwnd and user32.IsWindow(self.hwnd):
            user32.SetWindowPos(
                self.hwnd,
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
            )

    def on_live_card_click(self, hwnd):
        info = self.live_windows.get(hwnd)
        if not info or not user32.IsWindow(hwnd):
            return "break"

        now = time.monotonic()
        if now - info.get("last_click_ts", 0.0) < 0.18:
            return "break"
        info["last_click_ts"] = now

        is_minimized = bool(user32.IsIconic(hwnd))
        is_front = bool(info.get("in_front", False)) and not is_minimized

        if is_front:
            self._push_window_down(hwnd)
        else:
            self._bring_window_up(hwnd)

        self._refresh_dwm_thumbnails(force=True)
        return "break"

    def poll_multitask(self):
        if self.done:
            return
        try:
            self._poll_tick_count += 1
            if self._poll_tick_count % 12 == 0:
                if os.path.isfile(PID_FILE):
                    try:
                        with open(PID_FILE, "r", encoding="utf-8") as f:
                            sig = f.read().strip()
                            if sig in ("STOP", f"STOP:{os.getpid()}"):
                                self.quit()
                                return
                    except Exception:
                        pass
                else:
                    write_pid_file(self.hwnd)

            alt_down = bool(user32.GetAsyncKeyState(VK_MENU) & 0x8000)

            # Hotkey 1: Alt + Q -> Focus Note Editor
            q_down = bool(user32.GetAsyncKeyState(VK_Q) & 0x8000)
            if alt_down and q_down:
                if not self._q_was_down:
                    self._q_was_down = True
                    self.activate_note_hotkey()
            else:
                self._q_was_down = False

            # Hotkey 2: Alt + W -> Pin / Toggle Active Window
            w_down = bool(user32.GetAsyncKeyState(VK_W) & 0x8000)
            if alt_down and w_down:
                if not self._w_was_down:
                    self._w_was_down = True
                    self.quick_stash_hotkey()
            else:
                self._w_was_down = False

            # Hotkey 3: Alt + Z -> Collapse / Expand Sidebar
            z_down = bool(user32.GetAsyncKeyState(VK_Z) & 0x8000)
            if alt_down and z_down:
                if not self._z_was_down:
                    self._z_was_down = True
                    self.toggle_collapse()
            else:
                self._z_was_down = False

            fg = user32.GetForegroundWindow()
            if fg != self._last_checked_fg:
                self._last_checked_fg = fg
                if self._is_valid_external_window(fg):
                    self.last_external_hwnd = fg
                    if self.live_windows:
                        self._ensure_anti_occlusion_on_window(fg)
                        for h_p, p_info in self.live_windows.items():
                            new_front = (h_p == fg) and not bool(user32.IsIconic(h_p))
                            if p_info.get("in_front") != new_front:
                                p_info["in_front"] = new_front
                                self._update_card_visuals(h_p)

            for h_pinned, p_info in list(self.live_windows.items()):
                if user32.IsWindow(h_pinned) and user32.IsIconic(h_pinned) and p_info.get("in_front", False):
                    p_info["in_front"] = False
                    self._update_card_visuals(h_pinned)

            # Drag & Drop external window into Sidebar
            lbutton = bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
            pt = POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            sl, st, sr, sb = self.sidebar_rect
            cursor_in_sidebar = (not self.collapsed) and (sl + 6 <= pt.x <= sr) and (st <= pt.y <= sb)

            if lbutton:
                if not self._lbutton_was_down:
                    self._lbutton_was_down = True
                    if self._is_valid_external_window(fg) and not cursor_in_sidebar and not user32.IsIconic(fg):
                        self._drag_candidate_hwnd = fg
                        self._drag_start_pt = (pt.x, pt.y)
                        self._drag_candidate_was_zoomed = bool(user32.IsZoomed(fg))
                        self._drag_candidate_start_rect = (
                            get_normal_window_rect(fg)
                            if self._drag_candidate_was_zoomed
                            else get_window_rect(fg)
                        )
                        self._drag_is_moving = False
                    else:
                        self._drag_candidate_hwnd = None
                elif self._drag_candidate_hwnd and user32.IsWindow(self._drag_candidate_hwnd):
                    if user32.IsIconic(self._drag_candidate_hwnd):
                        self._drag_candidate_hwnd = None
                        self._drag_is_moving = False
                    else:
                        cur_r = get_window_rect(self._drag_candidate_hwnd)
                        sr0 = self._drag_candidate_start_rect
                        sx, sy = getattr(self, "_drag_start_pt", (pt.x, pt.y))
                        mouse_moved = math.hypot(pt.x - sx, pt.y - sy) > 20
                        if (
                            sr0
                            and cur_r[0] > -10000
                            and mouse_moved
                            and any(abs(a - b) > 10 for a, b in zip(cur_r, sr0))
                        ):
                            self._drag_is_moving = True
                        if self._drag_is_moving and cursor_in_sidebar:
                            if not self._drop_zone_active:
                                self._drop_zone_active = True
                                self.dock_title.config(text="DROP TO PIN", fg=self.GREEN)
                        elif self._drop_zone_active:
                            self._drop_zone_active = False
                            self.dock_title.config(text="WINDOWS", fg="#71717a")
            else:
                if self._lbutton_was_down:
                    if (
                        self._drag_candidate_hwnd
                        and self._drag_is_moving
                        and cursor_in_sidebar
                        and user32.IsWindow(self._drag_candidate_hwnd)
                        and not user32.IsIconic(self._drag_candidate_hwnd)
                    ):
                        h_drag = self._drag_candidate_hwnd
                        r0 = self._drag_candidate_start_rect
                        z0 = self._drag_candidate_was_zoomed
                        if r0:
                            ol, ot, or_, ob = r0
                            user32.SetWindowPos(
                                h_drag, HWND_TOP, ol, ot, max(400, or_ - ol), max(300, ob - ot), SWP_NOACTIVATE
                            )
                        if z0:
                            user32.ShowWindow(h_drag, SW_MAXIMIZE)
                        self.dock_live_window(h_drag)
                    if self._drop_zone_active:
                        self._drop_zone_active = False
                        self.dock_title.config(text="WINDOWS", fg="#71717a")
                self._lbutton_was_down = False
                self._drag_candidate_hwnd = None
                self._drag_is_moving = False
        except Exception:
            pass
        self.root.after(42, self.poll_multitask)

    def quick_stash_hotkey(self):
        fg = user32.GetForegroundWindow()
        target = fg if self._is_valid_external_window(fg) else self.last_external_hwnd
        if not target or not user32.IsWindow(target):
            return
        if target in self.live_windows:
            self.on_live_card_click(target)
        elif self._is_valid_external_window(target):
            self.dock_live_window(target)

    def stash_last_active_window(self):
        if self.last_external_hwnd and user32.IsWindow(self.last_external_hwnd):
            if self.last_external_hwnd in self.live_windows:
                self.on_live_card_click(self.last_external_hwnd)
            elif self._is_valid_external_window(self.last_external_hwnd):
                self.dock_live_window(self.last_external_hwnd)

    def dock_live_window(self, hwnd, orig_rect=None, orig_zoomed=None):
        """Pin window to 2-column grid (Zero-Move, Zero-Resize Z-Order control)."""
        if not hwnd or not user32.IsWindow(hwnd):
            return

        if hwnd in self.live_windows:
            self.on_live_card_click(hwnd)
            return

        if len(self.live_windows) >= 4:
            oldest = next(iter(self.live_windows))
            self.remove_live_window(oldest, restore=False)

        short_lbl = short_app_label(hwnd)

        hthumb = wintypes.HANDLE()
        hr = dwmapi.DwmRegisterThumbnail(self.hwnd, hwnd, ctypes.byref(hthumb))
        if hr != 0 or not hthumb:
            return

        self._ensure_anti_occlusion_on_window(hwnd)

        card = tk.Frame(
            self.dock_grid,
            bg="#0d0d12",
            highlightbackground="#272730",
            highlightthickness=1,
            padx=2,
            pady=2,
        )

        top_row = tk.Frame(card, bg="#0d0d12", height=18)
        top_row.pack(side="top", fill="x")

        dot_lbl = tk.Label(top_row, text="●", bg="#0d0d12", fg=self.GREEN, font=("Segoe UI", 7))
        dot_lbl.pack(side="left", padx=(2, 2))

        lbl = tk.Label(
            top_row,
            text=short_lbl,
            bg="#0d0d12",
            fg="#d4d4d8",
            font=("Segoe UI", 8, "bold"),
            cursor="hand2",
        )
        lbl.pack(side="left")

        close_lbl = tk.Label(
            top_row,
            text="×",
            bg="#0d0d12",
            fg="#71717a",
            padx=4,
            font=("Segoe UI", 8, "bold"),
            cursor="hand2",
        )
        close_lbl.pack(side="right")
        close_lbl.bind("<Button-1>", lambda e, h=hwnd: self.remove_live_window(h, restore=False))
        close_lbl.bind("<Enter>", lambda e: close_lbl.config(fg=self.RED))
        close_lbl.bind("<Leave>", lambda e: close_lbl.config(fg="#71717a"))

        act_lbl = tk.Label(
            top_row,
            text="↑ Top",
            bg="#14141c",
            fg=self.GREEN,
            padx=4,
            font=("Segoe UI", 7, "bold"),
            cursor="hand2",
        )
        act_lbl.pack(side="right", padx=2)
        act_lbl.bind("<Button-1>", lambda e, h=hwnd: self.on_live_card_click(h))

        preview_box = tk.Frame(card, bg="#000000", height=self.thumb_height, cursor="hand2")
        preview_box.pack(side="top", fill="x", pady=(1, 0))
        preview_box.pack_propagate(False)

        for widget in (card, top_row, dot_lbl, lbl, preview_box):
            widget.bind("<Button-1>", lambda e, h=hwnd: self.on_live_card_click(h))
            widget.bind("<MouseWheel>", self._on_dock_wheel)

        self.live_windows[hwnd] = {
            "hthumb": hthumb,
            "card": card,
            "preview": preview_box,
            "dot_lbl": dot_lbl,
            "act_lbl": act_lbl,
            "in_front": False,
            "last_click_ts": 0.0,
            "last_dest": None,
        }

        self._relayout_dock_grid()
        self._push_window_down(hwnd)
        self.root.update_idletasks()
        self._refresh_dwm_thumbnails(force=True)

    def _relayout_dock_grid(self):
        if not self.live_windows:
            self.dock_grid.pack_forget()
            self.dock_grid.config(height=1)
            return
        if not self.dock_grid.winfo_ismapped():
            self.dock_grid.pack(side="top", fill="x", pady=(3, 2))
        for idx, (hwnd, info) in enumerate(self.live_windows.items()):
            r, c = divmod(idx, 2)
            info["card"].grid(row=r, column=c, sticky="nsew", padx=3, pady=3)

    def _on_dock_wheel(self, event):
        delta = 8 if event.delta > 0 else -8
        self.thumb_height = max(64, min(180, self.thumb_height + delta))
        for info in self.live_windows.values():
            info["preview"].config(height=self.thumb_height)
        self.root.update_idletasks()
        self._refresh_dwm_thumbnails(force=True)
        return "break"

    def _refresh_dwm_thumbnails(self, force=False, query_source=False):
        dead = []
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()

        for hwnd, info in list(self.live_windows.items()):
            if not user32.IsWindow(hwnd):
                dead.append(hwnd)
                continue

            if self.collapsed:
                if info.get("last_dest") != "collapsed":
                    props = DWM_THUMBNAIL_PROPERTIES()
                    props.dwFlags = DWM_TNP_VISIBLE
                    props.fVisible = False
                    dwmapi.DwmUpdateThumbnailProperties(info["hthumb"], ctypes.byref(props))
                    info["last_dest"] = "collapsed"
                continue

            pbox = info["preview"]
            if not pbox.winfo_ismapped():
                continue

            px = pbox.winfo_rootx() - root_x
            py = pbox.winfo_rooty() - root_y
            pw = pbox.winfo_width()
            ph = pbox.winfo_height()
            if pw < 10 or ph < 10:
                continue

            cached_src = info.get("src_size")
            if force or query_source or not cached_src:
                src_size = SIZE()
                if (
                    dwmapi.DwmQueryThumbnailSourceSize(info["hthumb"], ctypes.byref(src_size)) == 0
                    and src_size.cx > 0
                    and src_size.cy > 0
                ):
                    cached_src = (src_size.cx, src_size.cy)
                    info["src_size"] = cached_src

            if cached_src:
                scx, scy = cached_src
                scale = min(pw / scx, ph / scy)
                tw = int(scx * scale)
                th = int(scy * scale)
                ox = px + (pw - tw) // 2
                oy = py + (ph - th) // 2
                dest_tuple = (ox, oy, ox + tw, oy + th)
            else:
                dest_tuple = (px, py, px + pw, py + ph)

            if not force and info.get("last_dest") == dest_tuple:
                continue
            info["last_dest"] = dest_tuple

            dest_rc = RECT(*dest_tuple)
            props = DWM_THUMBNAIL_PROPERTIES()
            props.dwFlags = (
                DWM_TNP_RECTDESTINATION
                | DWM_TNP_VISIBLE
                | DWM_TNP_OPACITY
                | DWM_TNP_SOURCECLIENTAREAONLY
            )
            props.rcDestination = dest_rc
            props.opacity = 255
            props.fVisible = True
            props.fSourceClientAreaOnly = False
            dwmapi.DwmUpdateThumbnailProperties(info["hthumb"], ctypes.byref(props))

        for h in dead:
            self.remove_live_window(h, restore=False)

    def remove_live_window(self, hwnd, restore=False):
        info = self.live_windows.pop(hwnd, None)
        if not info:
            return
        try:
            dwmapi.DwmUnregisterThumbnail(info["hthumb"])
        except Exception:
            pass
        try:
            info["card"].destroy()
        except Exception:
            pass

        self._relayout_dock_grid()
        if not self.live_windows:
            self._cleanup_layered_hwnds()

    # ------------------------------------------------------------------------
    # Multitasking Hotkeys & Collapse Pill Mode
    # ------------------------------------------------------------------------
    def _on_pill_press(self, event):
        self._pill_dragging = False
        self._pill_press_y = event.y_root
        self._pill_drag_offset_y = event.y_root - self.root.winfo_y()

    def _on_pill_drag(self, event):
        if not self.collapsed:
            return
        if abs(event.y_root - getattr(self, "_pill_press_y", event.y_root)) > 5:
            self._pill_dragging = True
            mon = pick_monitor(self.cfg.get("monitor", "2"))
            l, t, r, b = mon["rect"] if mon else (0, 0, 1920, 1080)
            pw, ph = 88, 28
            px = r - pw - 12
            py = max(t + 40, min(b - ph - 48, event.y_root - self._pill_drag_offset_y))
            self.cfg["pill_y"] = py
            self.sidebar_rect = (px, py, px + pw, py + ph)
            self.root.geometry(f"{pw}x{ph}{px:+d}{py:+d}")
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST, px, py, pw, ph, SWP_NOACTIVATE)

    def _on_pill_release(self, event):
        if getattr(self, "_pill_dragging", False):
            self._pill_dragging = False
            save_cfg(self.cfg)
            return
        self.toggle_collapse()

    def activate_note_hotkey(self):
        if self.collapsed:
            self.toggle_collapse()
        self.root.deiconify()
        user32.SetForegroundWindow(self.hwnd)
        self.root.focus_force()
        self.editor.focus_set()

    def return_to_previous_window(self, event=None):
        if self.last_external_hwnd and user32.IsWindow(self.last_external_hwnd):
            user32.SetForegroundWindow(self.last_external_hwnd)
        return "break"

    def toggle_collapse(self):
        self.collapsed = not self.collapsed
        if self.collapsed:
            self._refresh_dwm_thumbnails(force=True)
            self._restagger_stashed_windows()
            if self.registered:
                try:
                    shell32.SHAppBarMessage(ABM_REMOVE, ctypes.byref(self.abd))
                except Exception:
                    pass
                self.registered = False

            self.resize_grip.pack_forget()
            self.main_col.pack_forget()
            self.mini_pill.pack(fill="both", expand=True)

            mon = pick_monitor(self.cfg.get("monitor", "2"))
            l, t, r, b = mon["rect"] if mon else (0, 0, 1920, 1080)
            pw, ph = 88, 28
            default_py = t + int((b - t) * 0.78)
            saved_py = self.cfg.get("pill_y")
            py = int(saved_py) if (saved_py is not None and t + 40 <= int(saved_py) <= b - ph - 40) else default_py
            px = r - pw - 12
            self.sidebar_rect = (px, py, px + pw, py + ph)
            self.root.geometry(f"{pw}x{ph}{px:+d}{py:+d}")
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST, px, py, pw, ph,
                                SWP_NOACTIVATE | SWP_FRAMECHANGED)
            self.root.update_idletasks()
        else:
            self.mini_pill.pack_forget()
            self.resize_grip.pack(side="left", fill="y")
            self.main_col.pack(side="right", fill="both", expand=True)
            if self.mode == "docked":
                self.dock_sidebar()
            else:
                self.float_window()

    def _start_resize(self, event):
        if self.collapsed:
            return
        self._resizing = True
        self._float_resize_right = self.root.winfo_x() + self.root.winfo_width()

    def _do_resize(self, event):
        if not self._resizing or self.collapsed:
            return
        if self.mode == "docked" and self.mon_rect:
            l, t, r, b = self.mon_rect
            new_w = r - event.x_root
            self.width = max(340, min(1000, new_w))
            x = r - self.width
            h = b - t
            self.sidebar_rect = (x, t, r, b)
            self.root.geometry(f"{self.width}x{h}{x:+d}{t:+d}")
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST, x, t, self.width, h, SWP_NOACTIVATE)
        else:
            cur_y = self.root.winfo_y()
            cur_h = self.root.winfo_height()
            new_w = self._float_resize_right - event.x_root
            self.width = max(340, min(1000, new_w))
            new_x = self._float_resize_right - self.width
            self.sidebar_rect = (new_x, cur_y, self._float_resize_right, cur_y + cur_h)
            self.root.geometry(f"{self.width}x{cur_h}{new_x:+d}{cur_y:+d}")
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST, new_x, cur_y, self.width, cur_h, SWP_NOACTIVATE)

        self.root.update_idletasks()
        self._update_timer_ui()
        self._update_motivation_wraplength()
        self._refresh_dwm_thumbnails(force=True)

    def _end_resize(self, event):
        if not self._resizing:
            return
        self._resizing = False
        self.cfg["width"] = self.width
        save_cfg(self.cfg)
        if self.mode == "docked":
            self.dock_sidebar()

    # ------------------------------------------------------------------------
    # Docked AppBar & Floating Window Management
    # ------------------------------------------------------------------------
    def start_drag(self, event):
        if self.mode == "floating" and not self.collapsed:
            self._drag_x = event.x_root - self.root.winfo_x()
            self._drag_y = event.y_root - self.root.winfo_y()

    def do_drag(self, event):
        if self.mode == "floating" and not self.collapsed:
            new_x = event.x_root - self._drag_x
            new_y = event.y_root - self._drag_y
            cur_w = self.root.winfo_width()
            cur_h = self.root.winfo_height()
            self.sidebar_rect = (new_x, new_y, new_x + cur_w, new_y + cur_h)
            self.root.geometry(f"{cur_w}x{cur_h}{new_x:+d}{new_y:+d}")
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST, new_x, new_y, cur_w, cur_h, SWP_NOACTIVATE)
            self._refresh_dwm_thumbnails(force=True)

    def dock_sidebar(self):
        self.mode = "docked"
        self.cfg["mode"] = "docked"
        self.pin_btn.config(text="📌")

        mon = pick_monitor(self.cfg.get("monitor", "2"))
        if not mon:
            return
        l, t, r, b = mon["rect"]
        self.mon_rect = mon["rect"]

        if not self.registered:
            self.abd.uEdge = ABE_RIGHT
            self.abd.rc = RECT(r - self.width, t, r, b)
            shell32.SHAppBarMessage(ABM_NEW, ctypes.byref(self.abd))
            self.registered = True

        self.abd.uEdge = ABE_RIGHT
        self.abd.rc = RECT(r - self.width, t, r, b)
        shell32.SHAppBarMessage(ABM_QUERYPOS, ctypes.byref(self.abd))
        self.abd.rc.left = self.abd.rc.right - self.width
        shell32.SHAppBarMessage(ABM_SETPOS, ctypes.byref(self.abd))
        rc = self.abd.rc
        self.sidebar_rect = (rc.left, rc.top, rc.right, rc.bottom)
        self.mon_work = (l, t, rc.left, b)

        w = rc.right - rc.left
        h = rc.bottom - rc.top
        self.root.geometry(f"{w}x{h}{rc.left:+d}{rc.top:+d}")
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, rc.left, rc.top, w, h,
                            SWP_NOACTIVATE | SWP_FRAMECHANGED)
        self.root.update_idletasks()
        self._update_timer_ui()
        self._restagger_stashed_windows()
        self._refresh_dwm_thumbnails(force=True)

        mons = list_monitors()
        idx = next((i for i, m in enumerate(mons, 1) if m["rect"] == self.mon_rect), 0)
        self.title_lbl.config(text=f" SONIDE · M{idx}")

    def float_window(self):
        self.mode = "floating"
        self.cfg["mode"] = "floating"
        self.pin_btn.config(text="🗖")

        if self.registered:
            try:
                shell32.SHAppBarMessage(ABM_REMOVE, ctypes.byref(self.abd))
            except Exception:
                pass
            self.registered = False

        mon = pick_monitor(self.cfg.get("monitor", "2"))
        if mon:
            l, t, r, b = mon["rect"]
            self.mon_rect = mon["rect"]
            self.mon_work = mon["work"]
            x = l + (r - l - self.width) // 2
            y = t + 90
        else:
            x, y = 200, 120

        h = 680
        w = self.width
        self.sidebar_rect = (x, y, x + w, y + h)
        self.root.geometry(f"{w}x{h}{x:+d}{y:+d}")
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, x, y, w, h,
                            SWP_NOACTIVATE | SWP_FRAMECHANGED)
        self.root.update_idletasks()
        self.title_lbl.config(text=" SONIDE · FLOAT")
        self._refresh_dwm_thumbnails(force=True)

    def toggle_mode(self):
        if self.collapsed:
            self.toggle_collapse()
        if self.mode == "docked":
            self.float_window()
        else:
            self.dock_sidebar()
        save_cfg(self.cfg)

    def next_monitor(self):
        mons = list_monitors()
        if len(mons) < 2:
            return
        cur = next((i for i, m in enumerate(mons) if m["rect"] == self.mon_rect), -1)
        next_idx = (cur + 1) % len(mons) + 1
        self.cfg["monitor"] = str(next_idx)
        save_cfg(self.cfg)
        if self.registered:
            try:
                shell32.SHAppBarMessage(ABM_REMOVE, ctypes.byref(self.abd))
            except Exception:
                pass
            self.registered = False
        if self.collapsed:
            self.collapsed = False
            self.mini_pill.pack_forget()
            self.resize_grip.pack(side="left", fill="y")
            self.main_col.pack(side="right", fill="both", expand=True)
        if self.mode == "docked":
            self.dock_sidebar()
        else:
            self.float_window()

    # ------------------------------------------------------------------------
    # Quick Outline (# Heading Jump), Filter Todo & Clean Done Tasks
    # ------------------------------------------------------------------------
    def show_outline_menu(self, event=None):
        menu = tk.Menu(self.root, tearoff=0, bg="#141418", fg=self.FG,
                       activebackground=self.GREEN_DIM, activeforeground="#ffffff",
                       font=("Segoe UI", 9), bd=1, relief="solid")
        num_lines = int(self.editor.index("end-1c").split(".")[0])
        found = 0
        for ln in range(1, num_lines + 1):
            tags = set(self.editor.tag_names(f"{ln}.0")) | set(self.editor.tag_names(f"{ln}.1"))
            txt = self.editor.get(f"{ln}.0", f"{ln}.end").replace("\u200b", "").strip()
            if not txt:
                continue
            if "h1" in tags:
                menu.add_command(label=f"H1 · {txt}", command=lambda l=ln: self._jump_to_line(l))
                found += 1
            elif "h2" in tags:
                menu.add_command(label=f"   H2 · {txt}", command=lambda l=ln: self._jump_to_line(l))
                found += 1
            elif "h3" in tags:
                menu.add_command(label=f"      H3 · {txt}", command=lambda l=ln: self._jump_to_line(l))
                found += 1

        if not found:
            menu.add_command(label="(No headings)", state="disabled")

        x = self.outline_btn.winfo_rootx()
        y = self.outline_btn.winfo_rooty() + self.outline_btn.winfo_height() + 2
        menu.tk_popup(x, y)

    def _jump_to_line(self, line_num):
        self.editor.mark_set("insert", f"{line_num}.0")
        self.editor.see(f"{line_num}.0")
        self.editor.focus_set()

    def toggle_todo_filter(self):
        self.filter_todo_only = not self.filter_todo_only
        self.filter_btn.config(
            text="● Filtered" if self.filter_todo_only else "○ Pending",
            fg="#ffffff" if self.filter_todo_only else self.GREEN,
        )
        self._apply_todo_filter()

    def _apply_todo_filter(self):
        self.editor.tag_remove("elided_done", "1.0", "end")
        if not self.filter_todo_only:
            return
        num_lines = int(self.editor.index("end-1c").split(".")[0])
        for ln in range(1, num_lines + 1):
            if MarkdownEngine.line_checkbox_state(self.editor, ln) == "done":
                self.editor.tag_add("elided_done", f"{ln}.0", f"{ln + 1}.0")

    def collect_done_tasks(self):
        md = MarkdownEngine.dump_from_text(self.editor)
        lines = md.split("\n")
        active_lines = [l for l in lines if not (l.startswith("- [x] ") or l.startswith("- [X] "))]
        done_lines = [l for l in lines if (l.startswith("- [x] ") or l.startswith("- [X] "))]
        if not done_lines:
            return
        while active_lines and not active_lines[-1].strip():
            active_lines.pop()
        if active_lines and active_lines[-1] not in ("## Completed", "## Đã hoàn thành"):
            active_lines.append("")
            active_lines.append("## Completed")
        new_md = "\n".join(active_lines + done_lines)
        MarkdownEngine.load_to_text(self.editor, new_md, self.img_todo, self.img_done)
        self.save_notes(instant=True)

    def _update_task_stats(self):
        todo_c = len(self.editor.tag_ranges("check_todo_marker")) // 2
        done_c = len(self.editor.tag_ranges("check_done_marker")) // 2
        total = todo_c + done_c
        self.task_stat_lbl.config(
            text=f"{done_c}/{total}" if total > 0 else "",
            fg=self.GREEN if (total > 0 and done_c == total) else self.MUTED,
        )

    # ------------------------------------------------------------------------
    # Native Win32 Inline IME Composition (Fixes '[C|n]' White Box in tk.Text)
    # ------------------------------------------------------------------------
    def _install_inline_ime(self):
        """
        Tcl/Tk 8.6 (tkWinX.c) ignores WM_IME_STARTCOMPOSITION and WM_IME_COMPOSITION
        when GCS_RESULTSTR is not set, passing them to DefWindowProcW which spawns the
        legacy Windows default IME white box with bitmap SYSTEM_FONT (causing '[C|n]').
        Subclassing the Tk HWNDs renders GCS_COMPSTR inline directly inside self.editor!
        """
        self._subclassed_wndprocs = {}
        self._ime_wndproc_cb = WNDPROC(self._ime_wndproc)
        cb_addr = ctypes.cast(self._ime_wndproc_cb, ctypes.c_void_p).value
        for h in (self.root.winfo_id(), self.editor.winfo_id(), self.hwnd):
            if h and int(h) not in self._subclassed_wndprocs:
                orig = GetWindowLongPtrW(h, GWLP_WNDPROC)
                if orig:
                    self._subclassed_wndprocs[int(h)] = orig
                    SetWindowLongPtrW(h, GWLP_WNDPROC, cb_addr)

    def _uninstall_inline_ime(self):
        for h, orig in list(getattr(self, "_subclassed_wndprocs", {}).items()):
            try:
                if user32.IsWindow(h):
                    SetWindowLongPtrW(h, GWLP_WNDPROC, orig)
            except Exception:
                pass
        if hasattr(self, "_subclassed_wndprocs"):
            self._subclassed_wndprocs.clear()

    def _ime_wndproc(self, hwnd, msg, wparam, lparam):
        orig = self._subclassed_wndprocs.get(int(hwnd))
        if not orig:
            return 0
        try:
            if msg == WM_IME_SETCONTEXT:
                lparam = ctypes.c_ssize_t(lparam & ~ISC_SHOWUICOMPOSITIONWINDOW).value
                return user32.CallWindowProcW(orig, hwnd, msg, wparam, lparam)
            if msg == WM_IME_STARTCOMPOSITION:
                return 0
            if msg == WM_IME_COMPOSITION:
                self._handle_ime_composition(hwnd, lparam)
                return 0
            if msg == WM_IME_ENDCOMPOSITION:
                self.editor.tag_remove("ime_comp", "1.0", "end")
                return 0
        except Exception:
            pass
        return user32.CallWindowProcW(orig, hwnd, msg, wparam, lparam)

    def _ime_delete_comp_range(self):
        comp_ranges = self.editor.tag_ranges("ime_comp")
        if comp_ranges:
            start_idx = self.editor.index(comp_ranges[0])
            end_idx = self.editor.index(comp_ranges[-1])
            self.editor.mark_set("insert", start_idx)
            self.editor.delete(start_idx, end_idx)

    def _ime_insert_text(self, text, is_comp=False):
        if not text:
            return None
        try:
            if self.editor.tag_ranges("sel"):
                self.editor.delete("sel.first", "sel.last")
        except tk.TclError:
            pass

        ins_idx = self.editor.index("insert")
        line_num, col_str = ins_idx.split(".")
        col = int(col_str)

        line_tags = (
            set(self.editor.tag_names(f"{line_num}.0"))
            | set(self.editor.tag_names(f"{line_num}.1"))
            | set(self.editor.tag_names(f"{line_num}.2"))
        )
        inherit = [
            t for t in ("h1", "h2", "h3", "todo_line", "check_done", "bullet_line", "quote_line")
            if t in line_tags
        ]

        if col > 0:
            prev_tags = set(self.editor.tag_names("insert-1c"))
            for itag in ("bold", "highlight", "code"):
                if itag in prev_tags and itag not in inherit:
                    inherit.append(itag)

        if is_comp:
            inherit.append("ime_comp")

        start_idx = self.editor.index("insert")
        self.editor.insert("insert", text, tuple(inherit))
        self.editor.see("insert")
        return start_idx

    def _handle_ime_composition(self, hwnd, lparam):
        if self.done:
            return
        himc = imm32.ImmGetContext(hwnd)
        if not himc:
            return
        try:
            if lparam == 0:
                self._ime_delete_comp_range()
                self._schedule_idle_save()
                return

            if lparam & GCS_RESULTSTR:
                self._ime_delete_comp_range()
                byte_len = imm32.ImmGetCompositionStringW(himc, GCS_RESULTSTR, None, 0)
                if byte_len > 0:
                    n_chars = byte_len // 2
                    buf = ctypes.create_unicode_buffer(n_chars + 1)
                    imm32.ImmGetCompositionStringW(himc, GCS_RESULTSTR, buf, byte_len)
                    res_str = buf.value[:n_chars]
                    self._ime_insert_text(res_str, is_comp=False)

            if lparam & GCS_COMPSTR:
                self._ime_delete_comp_range()
                byte_len = imm32.ImmGetCompositionStringW(himc, GCS_COMPSTR, None, 0)
                if byte_len > 0:
                    n_chars = byte_len // 2
                    buf = ctypes.create_unicode_buffer(n_chars + 1)
                    imm32.ImmGetCompositionStringW(himc, GCS_COMPSTR, buf, byte_len)
                    comp_str = buf.value[:n_chars]
                    start_idx = self._ime_insert_text(comp_str, is_comp=True)
                    if start_idx and (lparam & GCS_CURSORPOS):
                        cur_pos = imm32.ImmGetCompositionStringW(himc, GCS_CURSORPOS, None, 0)
                        if 0 <= cur_pos <= n_chars:
                            self.editor.mark_set("insert", f"{start_idx}+{cur_pos}c")

            self._schedule_idle_save()
        except Exception:
            pass
        finally:
            imm32.ImmReleaseContext(hwnd, himc)

    def _finalize_ime_composition(self):
        for h in list(getattr(self, "_subclassed_wndprocs", {}).keys()):
            try:
                himc = imm32.ImmGetContext(h)
                if himc:
                    imm32.ImmNotifyIME(himc, NI_COMPOSITIONSTR, CPS_COMPLETE, 0)
                    imm32.ImmReleaseContext(h, himc)
            except Exception:
                pass
        self.editor.tag_remove("ime_comp", "1.0", "end")

    # ------------------------------------------------------------------------
    # Editor Live Markdown Events & Shortcuts
    # ------------------------------------------------------------------------
    def on_editor_click(self, event):
        self._finalize_ime_composition()
        user32.SetForegroundWindow(self.hwnd)
        self.editor.focus_set()
        idx = self.editor.index(f"@{event.x},{event.y}")
        line_num, col_str = idx.split(".")
        col = int(col_str)
        st = MarkdownEngine.line_checkbox_state(self.editor, line_num)
        if st and col <= 2:
            self._set_line_checkbox(line_num, checked=(st == "todo"))
            self.save_notes()
            return "break"
        return None

    def _set_line_checkbox(self, line_num, checked):
        self.editor.delete(f"{line_num}.0", f"{line_num}.2")
        MarkdownEngine.insert_checkbox(self.editor, f"{line_num}.0", checked, self.img_todo, self.img_done)
        if checked:
            self.editor.tag_remove("todo_line", f"{line_num}.2", f"{line_num}.end")
            self.editor.tag_add("check_done", f"{line_num}.2", f"{line_num}.end")
        else:
            self.editor.tag_remove("check_done", f"{line_num}.0", f"{line_num}.end")
            self.editor.tag_add("todo_line", f"{line_num}.2", f"{line_num}.end")
        self._apply_todo_filter()

    def _apply_heading_to_line(self, line_num, level, delete_to_idx):
        self.editor.delete(f"{line_num}.0", delete_to_idx)
        for h_tag in ("h1", "h2", "h3"):
            self.editor.tag_remove(h_tag, f"{line_num}.0", f"{line_num}.end+1c")
        rem = self.editor.get(f"{line_num}.0", f"{line_num}.end").replace("\u200b", "")
        self.editor.delete(f"{line_num}.0", f"{line_num}.end")
        # Wrap line in \u200b...\u200b sandwich so Tcl/Tk tk::TextInsert inherits the heading tag
        # on both sides of the insert cursor (even at end-1c on the very last line of the buffer).
        self.editor.insert(f"{line_num}.0", f"\u200b{rem}\u200b", (level,))
        self.editor.tag_add(level, f"{line_num}.0", f"{line_num}.end+1c")
        self.editor.mark_set("insert", f"{line_num}.1")

    def on_space_autoformat(self, event):
        cursor = self.editor.index("insert")
        line_num, col_str = cursor.split(".")
        raw_prefix = self.editor.get(f"{line_num}.0", cursor)
        prefix = raw_prefix.replace("\u200b", "")

        if prefix in ("#", "##", "###"):
            level = f"h{len(prefix)}"
            self._apply_heading_to_line(line_num, level, cursor)
            self._schedule_idle_save()
            return "break"

        if prefix in ("[]", "- [ ]", "[ ]"):
            self.editor.delete(f"{line_num}.0", cursor)
            MarkdownEngine.insert_checkbox(self.editor, f"{line_num}.0", False, self.img_todo, self.img_done)
            self._schedule_idle_save()
            return "break"

        if prefix in ("[x]", "- [x]", "[X]"):
            self.editor.delete(f"{line_num}.0", cursor)
            MarkdownEngine.insert_checkbox(self.editor, f"{line_num}.0", True, self.img_todo, self.img_done)
            self._schedule_idle_save()
            return "break"

        if prefix in ("-", "*"):
            self.editor.delete(f"{line_num}.0", cursor)
            self.editor.insert(f"{line_num}.0", "• ", ("bullet_prefix", "bullet_line"))
            self._schedule_idle_save()
            return "break"

        if prefix == ">":
            self.editor.delete(f"{line_num}.0", cursor)
            self.editor.insert(f"{line_num}.0", "▎ ", ("quote_bar", "quote_line"))
            self._schedule_idle_save()
            return "break"

        return None

    def on_enter(self, event):
        cursor = self.editor.index("insert")
        line_num = cursor.split(".")[0]
        line_text = self.editor.get(f"{line_num}.0", f"{line_num}.end").replace("\u200b", "")
        cb_state = MarkdownEngine.line_checkbox_state(self.editor, line_num)

        if line_text.strip() == "---":
            self.editor.delete(f"{line_num}.0", f"{line_num}.end")
            self.editor.insert(f"{line_num}.0", "────────────────────────────────────────\n", ("hr",))
            self._schedule_idle_save()
            return "break"

        if cb_state:
            if line_text.strip() == "":
                self.editor.delete(f"{line_num}.0", f"{line_num}.end")
                self._schedule_idle_save()
                return "break"
            self.editor.insert("insert", "\n")
            new_ln = str(int(line_num) + 1)
            MarkdownEngine.insert_checkbox(self.editor, f"{new_ln}.0", False, self.img_todo, self.img_done)
            self.editor.mark_set("insert", f"{new_ln}.2")
            self.editor.see("insert")
            self._schedule_idle_save()
            return "break"

        if line_text.startswith("• "):
            if line_text.strip() == "•":
                self.editor.delete(f"{line_num}.0", f"{line_num}.end")
                self._schedule_idle_save()
                return "break"
            self.editor.insert("insert", "\n• ", ("bullet_prefix", "bullet_line"))
            self.editor.see("insert")
            self._schedule_idle_save()
            return "break"

        tags_here = set(self.editor.tag_names(f"{line_num}.0")) | set(self.editor.tag_names(f"{line_num}.1"))
        if tags_here & {"h1", "h2", "h3"}:
            self.editor.insert("insert", "\n")
            new_ln = str(int(line_num) + 1)
            for ht in ("h1", "h2", "h3"):
                self.editor.tag_remove(ht, f"{new_ln}.0", f"{new_ln}.end+1c")
            new_raw = self.editor.get(f"{new_ln}.0", f"{new_ln}.end")
            if "\u200b" in new_raw:
                cleaned = new_raw.replace("\u200b", "")
                self.editor.delete(f"{new_ln}.0", f"{new_ln}.end")
                if cleaned:
                    self.editor.insert(f"{new_ln}.0", cleaned)
                self.editor.mark_set("insert", f"{new_ln}.0")
            self.editor.see("insert")
            self._schedule_idle_save()
            return "break"

        return None

    def on_backspace(self, event):
        cursor = self.editor.index("insert")
        line_num, col_str = cursor.split(".")
        col = int(col_str)
        cb_state = MarkdownEngine.line_checkbox_state(self.editor, line_num)
        if cb_state and col in (1, 2):
            self.editor.delete(f"{line_num}.0", f"{line_num}.2")
            self.editor.tag_remove("check_done", f"{line_num}.0", f"{line_num}.end")
            self.editor.tag_remove("todo_line", f"{line_num}.0", f"{line_num}.end")
            self._schedule_idle_save()
            return "break"

        # Allow Backspace at start of an empty heading line to revert to normal paragraph text
        tags_here = set(self.editor.tag_names(f"{line_num}.0")) | set(self.editor.tag_names(f"{line_num}.1"))
        if (tags_here & {"h1", "h2", "h3"}) and col <= 1:
            visible_txt = self.editor.get(f"{line_num}.0", f"{line_num}.end").replace("\u200b", "")
            if not visible_txt:
                self.editor.delete(f"{line_num}.0", f"{line_num}.end")
                for ht in ("h1", "h2", "h3"):
                    self.editor.tag_remove(ht, f"{line_num}.0", f"{line_num}.end+1c")
                self._schedule_idle_save()
                return "break"
        return None

    def shortcut_bold(self, event=None):
        self._toggle_tag("bold")
        self._schedule_idle_save()
        return "break"

    def shortcut_highlight(self, event=None):
        self._toggle_tag("highlight")
        self._schedule_idle_save()
        return "break"

    def shortcut_code(self, event=None):
        self._toggle_tag("code")
        self._schedule_idle_save()
        return "break"

    def _toggle_tag(self, tag_name):
        try:
            sel_start = self.editor.index("sel.first")
            sel_end = self.editor.index("sel.last")
            if tag_name in self.editor.tag_names(sel_start):
                self.editor.tag_remove(tag_name, sel_start, sel_end)
            else:
                self.editor.tag_add(tag_name, sel_start, sel_end)
            return
        except tk.TclError:
            pass

        w_start = self.editor.index("insert wordstart")
        w_end = self.editor.index("insert wordend")
        if self.editor.get(w_start, w_end).strip():
            if tag_name in self.editor.tag_names(w_start):
                self.editor.tag_remove(tag_name, w_start, w_end)
            else:
                self.editor.tag_add(tag_name, w_start, w_end)

    def shortcut_checkbox(self, event=None):
        line_num = self.editor.index("insert").split(".")[0]
        st = MarkdownEngine.line_checkbox_state(self.editor, line_num)
        if st == "todo":
            self._set_line_checkbox(line_num, True)
        elif st == "done":
            self.editor.delete(f"{line_num}.0", f"{line_num}.2")
            self.editor.tag_remove("check_done", f"{line_num}.0", f"{line_num}.end")
        else:
            MarkdownEngine.insert_checkbox(self.editor, f"{line_num}.0", False, self.img_todo, self.img_done)
            self.editor.tag_add("todo_line", f"{line_num}.2", f"{line_num}.end")
        self._schedule_idle_save()
        return "break"

    # ------------------------------------------------------------------------
    # Save & Load Notes
    # ------------------------------------------------------------------------
    def _schedule_idle_save(self):
        if self.save_timer:
            self.root.after_cancel(self.save_timer)
        self.save_timer = self.root.after(1500, self.save_notes)

    def on_key_release(self, event=None):
        """
        Zero-mutation KeyRelease handler for lag-free Vietnamese (UniKey/EVKey) input:
        - Never mutates self.editor during normal typing so IME backspace+insert sequences are uninterrupted.
        - Fallback heading detection if an IME committed '# ' / '## ' / '### ' directly.
        """
        if event and event.keysym in (
            "Up", "Down", "Left", "Right",
            "Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R",
        ):
            return

        if event and event.keysym == "space":
            cursor = self.editor.index("insert")
            line_num = cursor.split(".")[0]
            pre = self.editor.get(f"{line_num}.0", cursor).replace("\u200b", "")
            if pre in ("# ", "## ", "### "):
                level = f"h{len(pre.strip())}"
                self._apply_heading_to_line(line_num, level, cursor)

        self._schedule_idle_save()

    def load_notes(self):
        content = ""
        bak_path = f"{self.file_path}.bak"
        if os.path.isfile(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                content = ""
        if not content.strip() and os.path.isfile(bak_path):
            try:
                with open(bak_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                content = ""
        if not content.strip():
            content = (
                "# Workspace Notes\n\n"
                "- [ ] Key tasks for today\n"
            )
        MarkdownEngine.load_to_text(self.editor, content, self.img_todo, self.img_done)
        self._update_task_stats()
        self.editor.edit_reset()

    def save_notes(self, instant=False):
        if self.save_timer and not instant:
            try:
                self.root.after_cancel(self.save_timer)
            except Exception:
                pass
            self.save_timer = None

        try:
            markdown_data = MarkdownEngine.dump_from_text(self.editor).replace("\u200b", "")
            atomic_write_text(self.file_path, markdown_data)
            if markdown_data.strip():
                try:
                    atomic_write_text(f"{self.file_path}.bak", markdown_data)
                except Exception:
                    pass
            self.status_lbl.config(text=" · Saved", fg="#52525b")
        except Exception:
            self.status_lbl.config(text=" · Save Error", fg=self.RED)
        try:
            self._update_task_stats()
        except Exception:
            pass

    # ------------------------------------------------------------------------
    # Clean Exit
    # ------------------------------------------------------------------------
    def cleanup(self):
        if self.done:
            return
        self.done = True
        self.save_notes(instant=True)

        for hwnd in list(self.live_windows.keys()):
            try:
                self.remove_live_window(hwnd, restore=False)
            except Exception:
                pass
        self._cleanup_layered_hwnds()
        self._uninstall_inline_ime()

        if self.registered:
            try:
                shell32.SHAppBarMessage(ABM_REMOVE, ctypes.byref(self.abd))
            except Exception:
                pass
            self.registered = False

        try:
            if os.path.isfile(PID_FILE):
                with open(PID_FILE, "r", encoding="utf-8") as f:
                    cur_sig = f.read().strip()
                if cur_sig.startswith(f"{os.getpid()}:") or cur_sig in ("STOP", f"STOP:{os.getpid()}"):
                    os.remove(PID_FILE)
        except Exception:
            pass

    def quit(self):
        self.cleanup()
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.root.mainloop()


def main():
    ap = argparse.ArgumentParser(description="Sonide — Windows Multitasking Note Sidebar")
    ap.add_argument("--list", action="store_true", help="list monitors and exit")
    ap.add_argument("--choose", action="store_true", help="interactive monitor selection")
    ap.add_argument("--stop", action="store_true", help="stop running instance and exit")
    ap.add_argument("--monitor", help="monitor index (1, 2, ...) or primary")
    ap.add_argument("--width", type=int, help="sidebar width in pixels")
    ap.add_argument("--float", action="store_true", help="start in floating mode")
    args = ap.parse_args()

    enable_dpi_awareness()

    if args.stop:
        if stop_running_instance():
            print("Stopped Sonide and released desktop work area.")
        else:
            print("No running Sonide instance found.")
        return

    if args.list:
        for i, m in enumerate(list_monitors(), 1):
            l, t, r, b = m["rect"]
            print(f"Monitor {i}: {r - l}x{b - t} tai ({l},{t}){'  [chinh]' if m['primary'] else ''}")
        return

    is_interactive = bool(args.choose or (sys.stdin and hasattr(sys.stdin, "isatty") and sys.stdin.isatty()))
    h_mutex = acquire_single_instance(takeover=True)
    if not h_mutex:
        print("Ung dung dang chay ngam (dung stop.bat hoac --stop de tat).")
        return

    cfg = load_cfg()
    if args.monitor:
        cfg["monitor"] = args.monitor
        save_cfg(cfg)
    elif is_interactive and not args.float:
        choose_monitor_cli(cfg)

    if args.width:
        cfg["width"] = args.width
    if args.float:
        cfg["mode"] = "floating"

    app = NoteSidebarApp(cfg)

    def handle_signal(sig, frame):
        app.quit()
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
    except Exception:
        pass

    try:
        app.run()
    finally:
        if h_mutex:
            kernel32.CloseHandle(h_mutex)


if __name__ == "__main__":
    main()
