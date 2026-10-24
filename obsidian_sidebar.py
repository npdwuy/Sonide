# -*- coding: utf-8 -*-
"""
Obsidian Sidebar
================
Danh rieng mot dai o canh PHAI man hinh (AppBar - giong Taskbar) va dua cua so
Obsidian vao do. Windows se tru dai nay ra khoi vung lam viec, nen cua so khac
khi maximize chi chiem phan ben trai, khong bao gio de len Obsidian.

Chi dung thu vien co san cua Python (ctypes + tkinter), khong can pip install.

Cach dung:
    python obsidian_sidebar.py              chay binh thuong
    python obsidian_sidebar.py --list       liet ke cac monitor
    python obsidian_sidebar.py --monitor 2  ep dung monitor so 2
    python obsidian_sidebar.py --width 500  do rong dai (pixel that)

Cau hinh luu o config.json canh file nay (tu tao lan chay dau).
Muon dock app khac (Notepad, ...) chi can doi "process_name".
"""
import argparse
import atexit
import ctypes
import json
import os
import signal
import subprocess
import sys
import time
import traceback
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(HERE, "config.json")
LOG_PATH = os.path.join(HERE, "log.txt")
PID_FILE = os.path.join(HERE, ".sidebar.pid")

DEFAULT_CFG = {
    "process_name": "Obsidian.exe",   # app can dock
    "exe_path": "",                   # de trong = tu tim Obsidian
    "autolaunch": True,               # chua mo thi tu mo
    "monitor": "auto",                # "auto" = monitor roi lon nhat, hoac so 1,2,3...
    "width": 420,                     # do rong dai (pixel that)
    "header_height": 30,              # thanh nho tren cung chua nut
    "borderless": True,               # bo vien/thanh tieu de goc cua Obsidian
}

# ----------------------------------------------------------------------------
# Win32
# ----------------------------------------------------------------------------
if sys.platform != "win32":
    print("Chi chay tren Windows.")
    sys.exit(1)

user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

HWND = wintypes.HWND
LONG_PTR = ctypes.c_ssize_t


class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [("length", wintypes.UINT), ("flags", wintypes.UINT),
                ("showCmd", wintypes.UINT), ("ptMinPosition", POINT),
                ("ptMaxPosition", POINT), ("rcNormalPosition", RECT)]


class APPBARDATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", HWND),
                ("uCallbackMessage", wintypes.UINT), ("uEdge", wintypes.UINT),
                ("rc", RECT), ("lParam", wintypes.LPARAM)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]


WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, wintypes.LPARAM)
MONITORENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, ctypes.c_void_p, ctypes.c_void_p,
                                     ctypes.POINTER(RECT), wintypes.LPARAM)

user32.GetAncestor.argtypes = [HWND, wintypes.UINT]
user32.GetAncestor.restype = HWND
user32.IsWindow.argtypes = [HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsIconic.argtypes = [HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.IsZoomed.argtypes = [HWND]
user32.IsZoomed.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetWindowPlacement.argtypes = [HWND, ctypes.POINTER(WINDOWPLACEMENT)]
user32.GetWindowPlacement.restype = wintypes.BOOL
user32.SetWindowPlacement.argtypes = [HWND, ctypes.POINTER(WINDOWPLACEMENT)]
user32.SetWindowPlacement.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [HWND, HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.SetWindowPos.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.GetWindow.argtypes = [HWND, wintypes.UINT]
user32.GetWindow.restype = HWND
user32.SetForegroundWindow.argtypes = [HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL

GetWindowLongPtrW = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
GetWindowLongPtrW.argtypes = [HWND, ctypes.c_int]
GetWindowLongPtrW.restype = LONG_PTR

SetWindowLongPtrW = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
SetWindowLongPtrW.argtypes = [HWND, ctypes.c_int, LONG_PTR]
SetWindowLongPtrW.restype = LONG_PTR

user32.GetWindowTextW.argtypes = [HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = HWND
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.EnumDisplayMonitors.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                       MONITORENUMPROC, wintypes.LPARAM]
user32.EnumDisplayMonitors.restype = wintypes.BOOL
user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
user32.GetMonitorInfoW.restype = wintypes.BOOL

shell32.SHAppBarMessage.argtypes = [wintypes.DWORD, ctypes.POINTER(APPBARDATA)]
shell32.SHAppBarMessage.restype = ctypes.c_size_t

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE

ABM_NEW, ABM_REMOVE, ABM_QUERYPOS, ABM_SETPOS = 0, 1, 2, 3
ABE_RIGHT = 2
WM_APPBAR = 0x0400 + 1
GWL_STYLE, GWL_EXSTYLE = -16, -20
WS_CAPTION, WS_THICKFRAME = 0x00C00000, 0x00040000
WS_EX_TOOLWINDOW = 0x00000080
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER = 0x1, 0x2, 0x4
SWP_NOACTIVATE, SWP_FRAMECHANGED = 0x10, 0x20
SW_RESTORE = 9
GA_ROOT = 2
GW_OWNER = 4
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def stop_running_instance():
    """Dung tien trinh sidebar cu neu dang chay."""
    if not os.path.isfile(PID_FILE):
        return False
    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:
            old_pid = int(f.read().strip())
    except Exception:
        return False

    if old_pid == os.getpid():
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
        kernel32.TerminateProcess(h_proc, 0)
        kernel32.WaitForSingleObject(h_proc, 1500)
    finally:
        kernel32.CloseHandle(h_proc)

    try:
        if os.path.isfile(PID_FILE):
            os.remove(PID_FILE)
    except Exception:
        pass
    log(f"Da dong tien trinh cu PID {old_pid}")
    return True


def acquire_single_instance(name="Local\\ObsidianSidebarApp_Mutex", takeover=False):
    """Dam bao chi mot instance cua sidebar duoc chay tai mot thoi diem."""
    if takeover:
        stop_running_instance()
        time.sleep(0.3)

    m = kernel32.CreateMutexW(None, False, name)
    ERROR_ALREADY_EXISTS = 183
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        if takeover:
            # Thu lan 2 neu takeover dang giai phong handle
            if m:
                kernel32.CloseHandle(m)
            time.sleep(0.5)
            m = kernel32.CreateMutexW(None, False, name)
            if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
                if m:
                    kernel32.CloseHandle(m)
                return None
        else:
            if m:
                kernel32.CloseHandle(m)
            return None

    try:
        with open(PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass
    return m


def enable_dpi_awareness():
    """Lam viec bang pixel that, tranh bi Windows co gian toa do."""
    try:
        # Per-Monitor V2 (Windows 10 1607+)
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor V1
        return
    except Exception:
        pass
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass


def log(msg):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except Exception:
        pass


def load_cfg():
    cfg = dict(DEFAULT_CFG)
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except FileNotFoundError:
        save_cfg(cfg)
    except Exception as e:
        log("Loi doc config.json, dung mac dinh: %r" % e)
    return cfg


def save_cfg(cfg):
    try:
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log("Khong ghi duoc config.json: %r" % e)


def list_monitors():
    """Tra ve danh sach monitor, xep trai -> phai."""
    mons = []

    def cb(hmon, hdc, lprc, lparam):
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
        r = mi.rcMonitor
        mons.append({"rect": (r.left, r.top, r.right, r.bottom),
                     "primary": bool(mi.dwFlags & 1)})
        return True

    cb_proc = MONITORENUMPROC(cb)
    user32.EnumDisplayMonitors(None, None, cb_proc, 0)
    mons.sort(key=lambda m: (m["rect"][0], m["rect"][1]))
    return mons


def choose_monitor_cli(cfg):
    """Hien thi menu chon monitor truc tiep trong console va luu lua chon."""
    mons = list_monitors()
    if not mons:
        return
    if len(mons) == 1:
        cfg["monitor"] = "1"
        save_cfg(cfg)
        return

    cur_setting = cfg.get("monitor", "auto")
    cur_mon = pick_monitor(cur_setting)
    cur_idx = next((i for i, m in enumerate(mons, 1) if m["rect"] == (cur_mon["rect"] if cur_mon else None)), 1)

    print("========================================")
    print("   CHON MONITOR DE DOCK OBSIDIAN")
    print("========================================")
    for i, m in enumerate(mons, 1):
        l, t, r, b = m["rect"]
        is_pri = " [Chinh / Primary]" if m["primary"] else ""
        is_cur = "  <-- (Mac dinh dang chon)" if i == cur_idx else ""
        print(f"  [{i}] Monitor {i}: {r - l}x{b - t} tai ({l},{t}){is_pri}{is_cur}")
    print("----------------------------------------")

    try:
        prompt_str = f"Chon monitor (1-{len(mons)}) [Nhan Enter de dung Monitor {cur_idx}]: "
        ans = input(prompt_str).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nDa huy.")
        sys.exit(0)

    if ans.isdigit():
        val = int(ans)
        if 1 <= val <= len(mons):
            cur_idx = val

    cfg["monitor"] = str(cur_idx)
    save_cfg(cfg)
    l, t, r, b = mons[cur_idx - 1]["rect"]
    print(f"=> Da chon Monitor {cur_idx} ({r - l}x{b - t}). Dang khoi chay sidebar...\n")


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
    # "auto": Uu tien monitor chinh (primary)
    return next((m for m in mons if m["primary"]), mons[0])


def exe_name_of(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
        return ""
    finally:
        kernel32.CloseHandle(h)


def window_title(hwnd):
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value


def find_exe(cfg):
    if cfg.get("exe_path") and os.path.isfile(cfg["exe_path"]):
        return cfg["exe_path"]
    import shutil
    which_path = shutil.which(cfg.get("process_name", ""))
    if which_path:
        return which_path
    if cfg.get("process_name", "").lower() != "obsidian.exe":
        return ""
    for base in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles", ""),
                 os.environ.get("ProgramFiles(x86)", "")):
        if not base:
            continue
        for sub in ("Programs\\Obsidian\\Obsidian.exe", "Obsidian\\Obsidian.exe"):
            p = os.path.join(base, sub)
            if os.path.isfile(p):
                return p
    return ""


# ----------------------------------------------------------------------------
# App
# ----------------------------------------------------------------------------
class App:
    BG, FG, BTN = "#1e1e1e", "#c9c9c9", "#3a3a3a"

    def __init__(self, cfg):
        import tkinter as tk
        self.tk = tk
        self.cfg = cfg
        self.width = int(cfg["width"])
        self.header = int(cfg["header_height"])
        self.rect = (0, 0, 0, 0)       # vung AppBar da duoc Windows cap
        self.mon_rect = None
        self.target = None             # hwnd cua Obsidian dang dock
        self.saved = None
        self.launched = False
        self.registered = False
        self.done = False

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.configure(bg=self.BG)
        self.build_header()
        self.root.geometry("200x200+0+0")
        self.root.update_idletasks()
        self.hwnd = user32.GetAncestor(self.root.winfo_id(), GA_ROOT)

        self.abd = APPBARDATA()
        self.abd.cbSize = ctypes.sizeof(APPBARDATA)
        self.abd.hWnd = self.hwnd
        self.abd.uCallbackMessage = WM_APPBAR

        self.reserve()
        atexit.register(self.cleanup)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.tick()

    # ---- giao dien thanh nho tren cung ----
    def build_header(self):
        tk = self.tk
        bar = tk.Frame(self.root, bg=self.BG, height=self.header, cursor="arrow")
        bar.pack(side="top", fill="both", expand=True)
        bar.pack_propagate(False)
        title = self.cfg["process_name"].replace(".exe", "")
        self.title_text = "  " + title
        self.title_lbl = tk.Label(bar, text=self.title_text, bg=self.BG, fg=self.FG,
                                  font=("Segoe UI", 9, "bold"), cursor="hand2")
        self.title_lbl.pack(side="left")

        # Bam vao header de restore / focus cua so
        self.title_lbl.bind("<Button-1>", self.on_header_click)
        bar.bind("<Button-1>", self.on_header_click)

        def btn(text, cmd):
            b = tk.Label(bar, text=text, bg=self.BG, fg=self.FG, width=3,
                         font=("Segoe UI", 10), cursor="hand2")
            b.pack(side="right", fill="y")
            b.bind("<Button-1>", lambda e: cmd())
            b.bind("<Enter>", lambda e: b.config(bg=self.BTN))
            b.bind("<Leave>", lambda e: b.config(bg=self.BG))

        btn("✕", self.quit)                      # thoat
        btn("↻", self.regrab)                    # bat lai cua so
        btn("+", lambda: self.change_width(+40))
        btn("−", lambda: self.change_width(-40))
        btn("⇄", self.next_monitor)              # doi sang monitor khac

    def on_header_click(self, event=None):
        """Click chuot vao header se restore va focus cua so dang dock."""
        if self.target and user32.IsWindow(self.target):
            if user32.IsIconic(self.target):
                user32.ShowWindow(self.target, SW_RESTORE)
            user32.SetForegroundWindow(self.target)
            self.place(self.target)

    # ---- AppBar ----
    def reserve(self):
        mon = pick_monitor(self.cfg["monitor"])
        if mon is None:
            return
        l, t, r, b = mon["rect"]
        self.mon_rect = mon["rect"]

        # Truoc khi chuyen monitor hoac cap nhat, remove dang ky cu de tranh lam hong work area
        if self.registered:
            try:
                shell32.SHAppBarMessage(ABM_REMOVE, ctypes.byref(self.abd))
            except Exception:
                pass
            self.registered = False

        self.abd.uEdge = ABE_RIGHT
        self.abd.rc = RECT(r - self.width, t, r, b)
        shell32.SHAppBarMessage(ABM_NEW, ctypes.byref(self.abd))
        self.registered = True

        shell32.SHAppBarMessage(ABM_QUERYPOS, ctypes.byref(self.abd))
        self.abd.rc.left = self.abd.rc.right - self.width
        shell32.SHAppBarMessage(ABM_SETPOS, ctypes.byref(self.abd))
        rc = self.abd.rc
        self.rect = (rc.left, rc.top, rc.right, rc.bottom)

        # Dat vi tri thanh header (chi chiem header_height tren cung de khong de len Obsidian)
        w = rc.right - rc.left
        h = self.header
        user32.SetWindowPos(self.hwnd, None, rc.left, rc.top, w, h,
                            SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)
        self.root.geometry(f"{w}x{h}{rc.left:+d}{rc.top:+d}")
        self.root.update_idletasks()

        mons = list_monitors()
        idx = next((i for i, m in enumerate(mons, 1) if m["rect"] == self.mon_rect), 0)
        self.title_lbl.config(text="%s  ·  monitor %d/%d" % (self.title_text, idx, len(mons)))
        if self.target:
            self.place(self.target)

    def next_monitor(self):
        mons = list_monitors()
        if len(mons) < 2:
            return
        cur = next((i for i, m in enumerate(mons) if m["rect"] == self.mon_rect), -1)
        self.cfg["monitor"] = str((cur + 1) % len(mons) + 1)
        save_cfg(self.cfg)
        self.reserve()

    def change_width(self, delta):
        self.width = max(240, min(1000, self.width + delta))
        self.cfg["width"] = self.width
        save_cfg(self.cfg)
        self.reserve()

    # ---- tim / dock cua so ----
    def find_target(self):
        want = self.cfg["process_name"].lower()
        found = []

        def cb(hwnd, lparam):
            if hwnd == self.hwnd or not user32.IsWindow(hwnd):
                return True
            if not user32.IsWindowVisible(hwnd):
                return True
            # Bo qua cua so con / owned dialog popup
            if user32.GetWindow(hwnd, GW_OWNER):
                return True
            # Bo qua tool window / tooltip
            ex = GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
            if ex & WS_EX_TOOLWINDOW:
                return True
            title = window_title(hwnd)
            if not title or title in ("Default IME", "MSCTFIME UI"):
                return True
            if exe_name_of(hwnd) == want:
                found.append(hwnd)
            return True

        cb_proc = WNDENUMPROC(cb)
        user32.EnumWindows(cb_proc, 0)
        return found[0] if found else None

    def attach(self, hwnd):
        if not hwnd or not user32.IsWindow(hwnd):
            return
        if self.target == hwnd:
            return

        # Lay vi tri that (unminimized) cua cua so de restore khi detach
        wp = WINDOWPLACEMENT()
        wp.length = ctypes.sizeof(WINDOWPLACEMENT)
        has_wp = user32.GetWindowPlacement(hwnd, ctypes.byref(wp))
        if has_wp and (wp.rcNormalPosition.right > wp.rcNormalPosition.left):
            nr = wp.rcNormalPosition
            saved_rect = (nr.left, nr.top, nr.right, nr.bottom)
        else:
            rc = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rc))
            saved_rect = (rc.left, rc.top, rc.right, rc.bottom)

        style = GetWindowLongPtrW(hwnd, GWL_STYLE)
        self.saved = {"style": style, "rect": saved_rect}
        self.target = hwnd

        if self.cfg.get("borderless", True):
            SetWindowLongPtrW(hwnd, GWL_STYLE, style & ~(WS_CAPTION | WS_THICKFRAME))

        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)

        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)

        self.place(hwnd)
        log("Da dock cua so %s: %r" % (hex(int(hwnd)), window_title(hwnd)))

    def place(self, hwnd):
        if not hwnd or not user32.IsWindow(hwnd):
            return
        # Neu nguoi dung chu dong minimize Obsidian thi khong ep restore lien tuc
        if user32.IsIconic(hwnd):
            return
        if user32.IsZoomed(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)

        l, t, r, b = self.rect
        x, y, w, h = l, t + self.header, r - l, b - t - self.header
        rc = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rc))
        if (rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top) != (x, y, w, h):
            user32.SetWindowPos(hwnd, None, x, y, w, h,
                                SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)

    def detach(self):
        hwnd, s = self.target, self.saved
        self.target, self.saved = None, None
        if not hwnd or not s or not user32.IsWindow(hwnd):
            return
        SetWindowLongPtrW(hwnd, GWL_STYLE, s["style"])
        l, t, r, b = s["rect"]
        w = max(400, r - l)
        h = max(300, b - t)
        if l < -20000 or t < -20000:
            if self.mon_rect:
                ml, mt, mr, mb = self.mon_rect
                l, t = ml + 100, mt + 100
            else:
                l, t = 100, 100
        user32.SetWindowPos(hwnd, None, l, t, w, h,
                            SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)

    def regrab(self):
        self.detach()

    # ---- vong lap ----
    def tick(self):
        if self.done:
            return
        try:
            mon = pick_monitor(self.cfg["monitor"])
            if mon and mon["rect"] != self.mon_rect:
                self.reserve()

            if self.target and not user32.IsWindow(self.target):
                self.target, self.saved = None, None
                # Neu app da duoc mo ma sau do dong hoan toan -> tu dong dong sidebar
                if self.launched and not self.find_target():
                    log("App can dock da dong, tu dong thoat sidebar.")
                    self.quit()
                    return

            if not self.target:
                hwnd = self.find_target()
                if hwnd:
                    self.attach(hwnd)
                elif self.cfg.get("autolaunch") and not self.launched:
                    exe = find_exe(self.cfg)
                    self.launched = True
                    if exe:
                        subprocess.Popen([exe], close_fds=True)
                        log("Da mo " + exe)
                    else:
                        log("Khong thay file exe, hay mo app bang tay hoac dien exe_path.")
            else:
                self.place(self.target)
        except Exception:
            log("Loi trong tick:\n" + traceback.format_exc())
        self.root.after(800, self.tick)

    # ---- thoat ----
    def cleanup(self):
        if self.done:
            return
        self.done = True
        try:
            self.detach()
        except Exception:
            log("Loi detach:\n" + traceback.format_exc())
        if self.registered:
            try:
                shell32.SHAppBarMessage(ABM_REMOVE, ctypes.byref(self.abd))
            except Exception:
                pass
            self.registered = False
        try:
            if os.path.isfile(PID_FILE):
                with open(PID_FILE, "r", encoding="utf-8") as f:
                    if f.read().strip() == str(os.getpid()):
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
    ap = argparse.ArgumentParser(description="Dock Obsidian vao canh phai man hinh")
    ap.add_argument("--list", action="store_true", help="liet ke monitor roi thoat")
    ap.add_argument("--choose", action="store_true", help="hien menu chon monitor trong console")
    ap.add_argument("--stop", action="store_true", help="dung tien trinh sidebar dang chay roi thoat")
    ap.add_argument("--monitor", help="so monitor (1,2,..) hoac auto")
    ap.add_argument("--width", type=int, help="do rong dai, pixel that")
    args = ap.parse_args()

    enable_dpi_awareness()

    if args.stop:
        stopped = stop_running_instance()
        if stopped:
            print("Da tat tien trinh Obsidian Sidebar.")
        else:
            print("Khong co tien trinh Obsidian Sidebar nao dang chay.")
        return

    if args.list:
        for i, m in enumerate(list_monitors(), 1):
            l, t, r, b = m["rect"]
            print("Monitor %d: %dx%d tai (%d,%d)%s" %
                  (i, r - l, b - t, l, t, "  [chinh]" if m["primary"] else ""))
        return

    is_interactive = bool(args.choose or (sys.stdin and hasattr(sys.stdin, "isatty") and sys.stdin.isatty()))

    # Kiem tra single instance: neu chay tu console thi takeover tien trinh cu de khong bi chan
    h_mutex = acquire_single_instance(takeover=is_interactive)
    if not h_mutex:
        log("Tien trinh obsidian_sidebar khac da dang chay. Bo qua.")
        print("Ung dung dang chay ngam (dung stop.bat hoac --stop neu muon tat).")
        return

    cfg = load_cfg()
    if args.monitor:
        cfg["monitor"] = args.monitor
        save_cfg(cfg)
    elif is_interactive:
        choose_monitor_cli(cfg)

    if args.width:
        cfg["width"] = args.width

    app = App(cfg)

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
    try:
        main()
    except Exception:
        log("Loi nghiem trong:\n" + traceback.format_exc())
        raise
