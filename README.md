# Sonide

Minimalist Windows Multitasking Note Sidebar with live WYSIWYG Markdown, Focus Timer, and 24fps DWM Live Window Previews.

## Features
- **Docked Windows AppBar & Floating Mode:** Reserves dedicated screen edge space (`SHAppBarMessage`) or collapses into a compact floating pill (`Alt + Z`).
- **Live WYSIWYG Markdown Editor:** Supports `#` / `##` / `###` headings, interactive rounded checkboxes (`- [ ]` / `- [x]`), bold (`Ctrl + B`), highlight (`Ctrl + H`), inline code (`Ctrl + E`), zoom (`Ctrl + MouseWheel`), and native Win32 inline IME composition for Vietnamese input.
- **2-Column Live Window Grid:** Pin external windows via drag-and-drop or `Alt + W` with 24fps DWM live thumbnail previews and zero-move/zero-resize Z-order layering.
- **Focus Timer:** Built-in countdown timer with progress bar and quick presets (`15m`, `25m`, `45m`).

## Quick Start
- Start in background: `start.bat` (or `pyw note_sidebar.py`)
- Stop running instance: `stop.bat` (or `py note_sidebar.py --stop`)

## Hotkeys
- `Alt + Q`: Focus note editor (`Esc` returns to previous active window)
- `Alt + W`: Pin or toggle active window in the Live Window Grid
- `Alt + Z`: Collapse or expand the sidebar
