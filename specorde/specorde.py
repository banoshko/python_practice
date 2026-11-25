#This is my attempt at making an actually sellable product.
#Not even 2 weeks into python at this point
#Start - Sunday, 27th Sep. 2026

from datetime import datetime
from pathlib import Path
import hashlib
import os
import sys
import tkinter as tk
import customtkinter as ctk
import time
import re
import tempfile
from logging.handlers import RotatingFileHandler
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageOps, ImageChops, ImageFilter, ImageStat, ImageEnhance, ImageDraw
import json
import threading
import logging
from collections import Counter, OrderedDict, deque
import queue
from send2trash import send2trash
import ctypes
from ctypes import wintypes
import io
import shutil
import math
import numpy as np

#version
app_version = "1.1.0.0"

#Developer settings
month_dict = {
    1: "01 January", 2: "02 February", 3: "03 March", 4: "04 April", 5: "05 May", 6: "06 June", 7: "07 July", 8: "08 August", 9: "09 September", 10: "10 October", 11: "11 November", 12: "12 December"
}
q = queue.Queue()
cfg = {}
check = 1
frames_loaded = False
def make_app_folder():
    for base in (os.getenv("APPDATA"), Path.home(), tempfile.gettempdir()):
        if not base:
            continue
        try:
            folder = Path(base) / "Specorde"
            folder.mkdir(parents=True, exist_ok=True)
            return folder
        except OSError:
            continue
    return Path(tempfile.gettempdir())

path = make_app_folder()
try:
    log_handler = RotatingFileHandler(path / "specorde.log", maxBytes=1_000_000, backupCount=1, encoding="utf-8")
except OSError:
    log_handler = logging.NullHandler()

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    heif_ok = True
except Exception:
    heif_ok = False

try:
    import rawpy
    raw_ok = True
except Exception:
    raw_ok = False

try:
    import exifread
    exifread_ok = True
except Exception:
    exifread_ok = False

log_handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s", "%H:%M:%S"))
logging.basicConfig(level=logging.INFO, handlers=[log_handler])
logging.info("Specorde %s started", app_version)
logging.info("HEIC support: %s, RAW support: %s, RAW dates: %s", heif_ok, raw_ok, exifread_ok)
def log_crash(exc, val, tb):
    logging.critical("Crashed", exc_info=(exc, val, tb))
sys.excepthook = log_crash
memory = path / "memory.json"
journal_path = path / "journals"
journal_name = None
size = 1
sizes = {0: (108, 144, 5), 1: (138, 184, 4), 2: (188, 251, 3)}
dry_run = 0

tutorial_seen = 0
try:
    with open(memory, "r", encoding="utf-8") as f:
        tutorial_seen = json.load(f)
except FileNotFoundError:
    logging.info("memory.json not found, starting fresh.")
except (OSError, json.JSONDecodeError):
    logging.warning("memory.json unreadable, starting fresh.")
if tutorial_seen not in (0, 1):
    tutorial_seen = 0

if tutorial_seen == 0:
    currently_open = 1
else:
    currently_open = 0  

settings_file = path / "settings.json"
settings = {}

def settings_load():
    global settings
    try:
        with open(settings_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        settings = data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        settings = {}

def setting_get(key, default=None):
    return settings.get(key, default)

def setting_set(key, value):
    settings_load()
    settings[key] = value
    tmp = settings_file.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(settings, f)
        os.replace(tmp, settings_file)
    except OSError:
        logging.exception("Could not save settings.")
heif_suffixes = {".heic", ".heif"}
raw_suffixes = {".cr2", ".cr3", ".nef", ".nrw", ".arw", ".dng", ".orf", ".rw2", ".raf", ".pef", ".srw"}
exif_suffix = {".jpg", ".jpeg", ".tiff", ".tif"} | heif_suffixes | raw_suffixes
#Script itself
def start_execute(task):
    threading.Thread(target=task, daemon=True).start()

def lock_ui():
    for b in (execute_button, folder_browser, restore_button, dry_run_button):
        b.configure(fg_color="#173348", state="disabled")

def run_execute():
    global cfg
    if "target_folder" not in globals():
        q.put(("status", "You must pick a folder."))
        q.put(("status_reset", None))
        return
    
    if not (actions_find.get() or actions_sort.get() or actions_rename.get()):
        q.put(("status", "Tick at least one function."))
        q.put(("status_reset", None))
        return
    if actions_rename.get() and settings_rename_pattern.get() == "custom name + number":
        custom_check()
        if check == 0:
            messagebox.showwarning("Specorde", "Your custom name is not valid. Check it in Settings.")
            return
    if not target_folder.is_dir():
        messagebox.showwarning("Specorde", "That folder no longer exists. Please choose it again.")
        return
    if target_folder.name in ("sorted_specorde", "duplicates_specorde", "rejected_specorde", "kept_specorde"):
        messagebox.showwarning("Specorde", "This is a Specorde output folder. Pick the folder that contains it, then use 'Restore folder' to put its files back.")
        return
    if not dry_run:
        try:
            count = sum(1 for f in target_folder.iterdir() if f.is_file() and not is_protected_item(f))
        except OSError:
            messagebox.showwarning("Specorde", "Can't read that folder. Please pick another folder.")
            return
        plural = "" if count == 1 else "s"
        message = f"This will change files in '{target_folder.name or target_folder}' ({count} file{plural})."
        if actions_find.get() and settings_duplicate_delete.get() == "Deleted":
            message += "\n\nDuplicates will be sent to the Recycle Bin. On USB or network drives they may be deleted permanently!"
        if not messagebox.askyesno("Specorde", message + "\n\nContinue?"):
            return
    cfg = {
        "find": actions_find.get(),
        "sort": actions_sort.get(),
        "rename": actions_rename.get(),
        "sortby": settings_sort_sortby.get(),
        "structure": settings_sort_structure.get(),
        "duplicate_mode": settings_duplicate_delete.get(),
        "pattern": settings_rename_pattern.get(),
        "renameby": settings_rename_renameby.get(),
        "custom": settings_rename_custom.get("1.0", "end-1c"),
    }
    lock_ui()
    start_execute(execute)
reset_job = None
SUMMARY_COLOR = "#c8ccd8"
PANEL_COLOR = "#1f2029"
FADE_STEPS = 10
PREVIEW_LIMIT = 150
preview_count = 0
preview_removed = set()

def mix(c1, c2, t):
    a = [int(c1[i:i+2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i+2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))

SUMMARY_LINE_TIME = 850
summary_labels = []
summary_jobs = []

def summary_clear():
    for job in summary_jobs:
        canvas.after_cancel(job)
    summary_jobs.clear()
    for label in summary_labels:
        label.destroy()
    summary_labels.clear()
    bar_summary.grid_forget()

def summary_add(line):
    label = ctk.CTkLabel(bar_summary, text=line, text_color=SUMMARY_COLOR, font=("Bahnschrift Light Condensed", 15), justify="left", anchor="w", wraplength=200)
    summary_labels.append(label)
    for row, item in enumerate(reversed(summary_labels)):
        item.grid(row=row, column=0, sticky="w")
    bar_summary.grid(row=5, column=0, sticky="nw", padx=20, pady=5)

def summary_fade(label, step=0):
    if step > FADE_STEPS:
        return
    label.configure(text_color=mix(SUMMARY_COLOR, PANEL_COLOR, step / FADE_STEPS))
    summary_jobs.append(canvas.after(40, lambda: summary_fade(label, step + 1)))

def summary_hide_later():
    for position, label in enumerate(summary_labels, start=1):
        summary_jobs.append(canvas.after(SUMMARY_LINE_TIME * position, lambda l=label: summary_fade(l)))
    end = SUMMARY_LINE_TIME * len(summary_labels) + FADE_STEPS * 40 + 100
    summary_jobs.append(canvas.after(end, summary_clear))

def check_messages():
    global reset_job
    try:
        while True:
            kind, value = q.get_nowait()
            if kind == "status":
                if reset_job is not None:
                    canvas.after_cancel(reset_job)
                    reset_job = None
                status.configure(text=value)
            elif kind == "bar_text":
                bar_text.configure(text=value)
            elif kind == "bar_text_destroy":
                bar_text.grid_forget()
            elif kind == "bar_destroy":
                bar.grid_forget()
            elif kind == "bar_set":
                bar.set(value)
            elif kind == "bar_show":
                bar.grid(row=0, column=0, padx=25, sticky="w", pady=(8,2))
                bar.set(0)
                bar_text.configure(text="0%")
            elif kind == "bar_text_show":
                bar_text.grid(row=1, column=0, padx=32, sticky="w")
            elif kind == "bar_hide":
                bar.grid_forget()
            elif kind == "bar_text_hide":
                bar_text.grid_forget()
            elif kind == "summary_clear":
                summary_clear()
            elif kind == "summary_add":
                summary_add(value)
            elif kind == "summary_hide_later":
                summary_hide_later()
            elif kind == "status_reset":
                if reset_job is not None:
                    canvas.after_cancel(reset_job)
                reset_job = canvas.after(1700, lambda: status.configure(text="Sitting..."))
            elif kind == "suggest":
                suggest_apply(*value)
            elif kind == "suggest_progress":
                suggest_progress(*value)
            elif kind == "folder_reset":
                folder_browser.configure(text="Choose a new folder")
                folder_chosen.configure(text="...")
            elif kind == "lock":
                execute_button.configure(fg_color="#173348", state="disabled")
                folder_browser.configure(fg_color="#173348", state="disabled")
                restore_button.configure(fg_color="#173348", state="disabled")
                dry_run_button.configure(fg_color="#173348", state="disabled")
            elif kind == "unlock":
                execute_button.configure(fg_color="#1f6aa5", state="normal")
                folder_browser.configure(fg_color="#1f6aa5", state="normal")
                restore_button.configure(fg_color="#1f6aa5", state="normal")
                dry_run_button.configure(fg_color="#1f6aa5", state="normal")
    except queue.Empty: pass
    finally: canvas.after(15, check_messages)

def parse_exif_date(text):
    try:
        return datetime.strptime(text.strip("\x00 "), "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None

def mark():
    return "○ " if dry_run else "✓ "

def result(count, thing, verb, failed=0):
    n = f"{count} {thing}" + ("" if count == 1 else "s")
    text = f"{n} would be {verb}" if dry_run else f"{n} {verb}"
    if failed:
        text += f" ({failed} failed)"
    return ("✗ " if failed else mark()) + text + "."

def short(p):
    try:
        return str(Path(p).relative_to(target_folder))
    except ValueError:
        return str(p)

def log_preview(text):
    global preview_count
    preview_count += 1
    if preview_count <= PREVIEW_LIMIT:
        logging.info("[PREVIEW] %s", text)
    elif preview_count == PREVIEW_LIMIT + 1:
        logging.info("[PREVIEW] ... more not listed (the summary has the full count)")

def safe_rename(item, destination):
    if dry_run:
        log_preview(f"{item.name}  ->  {short(destination)}")
        return True
    try:
        with open(journal_name, "a", encoding="utf-8") as f:
            f.write(json.dumps({"from": str(item), "to": str(destination)}) + "\n")
    except OSError:
        logging.exception("Could not write journal, leaving %s untouched.", item.name)
        return False
    try:
        item.rename(destination)
    except OSError:
        logging.exception("Could not move or rename %s.", item.name)
        return False
    logging.debug("Moved %s -> %s", item.name, short(destination))
    return True

def remove_duplicate(file, mode):
    if dry_run:
        preview_removed.add(file)
    if mode == "Moved to a folder":
        if not dry_run:
            duplicates.mkdir(exist_ok=True)
        destination = duplicates / file.name
        counter = 1
        while destination.exists():
            destination = duplicates / f"{file.stem}_{counter}{file.suffix}"
            counter += 1
        return safe_rename(file, destination)
    if dry_run:
        log_preview(f"{file.name}  ->  Recycle Bin")
        return True
    send2trash(str(file))
    return True

def find_last_run():
    try:
        for file in sorted(journal_path.glob("run_*.jsonl"), reverse=True):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    header = json.loads(f.readline())
                    has_entries = bool(f.readline().strip())

                if not isinstance(header, dict):
                    logging.error("Invalid journal header: %s", file.name)
                    continue

                if not has_entries:
                    continue

            except (OSError, json.JSONDecodeError):
                logging.exception("Could not read journal: %s", file.name)
                continue

            if header.get("folder") == str(target_folder):
                return file
        return None
    except (FileNotFoundError, PermissionError):
        return None

def clean_old_journals(days=30):
    try:
        old_files = list(journal_path.glob("run_*.used"))
    except OSError:
        return
    limit = time.time() - days * 86400
    for old in old_files:
        try:
            if old.stat().st_mtime < limit:
                old.unlink()
        except OSError:
            logging.exception("Could not delete old journal %s.", old.name)

def get_exif(path):
    if path.suffix.lower() in raw_suffixes:
        return exif_from_exifread(path)[0] or exif_from_raw_preview(path)[0] or None
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if exif:
                date_str = None
                try:
                    date_str = exif.get_ifd(0x8769).get(36867)
                except Exception: pass
                date_str = date_str or exif.get(36867) or exif.get(306)
                if not date_str:
                    try:
                        exif_ifd = exif.get_ifd(0x8769)
                        date_str = exif_ifd.get(36867) or exif_ifd.get(306)
                    except Exception: pass
                if date_str:
                    if isinstance(date_str, bytes):
                        return date_str.decode('utf-8', errors='ignore').strip()
                    return str(date_str).strip()
    except Exception: pass
    return None


def get_file_date(item, mode):
    if mode == "Date taken":
        if item.suffix.lower() in exif_suffix:
            exif_string = get_exif(item)
            photo_date = parse_exif_date(exif_string) if exif_string else None
            if photo_date:
                return photo_date
            logging.warning("No date taken for %s, using date modified instead.", item.name)
        else:
            logging.debug("%s has an unsupported suffix, using date modified.", item.name)
    return datetime.fromtimestamp(item.stat().st_mtime)

last_progress = 0.0

def progress(label, done, total):
    global last_progress
    now = time.perf_counter()
    if now - last_progress < 0.1:
        return
    last_progress = now
    percent = min(done / total * 100, 100)
    q.put(("status", "Almost there!" if percent > 80 else label))
    q.put(("bar_text", f"{percent:.2f}%"))
    q.put(("bar_set", percent / 100))

def bar_start():
    global last_progress
    last_progress = 0.0
    q.put(("bar_set", 0))

def sort():
    files = list_files(target_folder)
    if not files:
        return mark() + "No files to sort."
    total = sum(s for _, s in files) or 1
    done = 0
    sorted_count = 0
    failed = 0
    bar_start()

    for item, item_size in files:
        done += item_size
        progress("Sorting...", done, total)

        try:
            file_time = get_file_date(item, cfg["sortby"])
            month_dir = sorted_dir / str(file_time.year) / month_dict[file_time.month]
            if cfg["structure"] == "year/month/day":
                destination_dir = month_dir / f"{file_time.day:02d}"
            else:
                destination_dir = month_dir
            if not dry_run:
                destination_dir.mkdir(parents=True, exist_ok=True)

            destination = destination_dir / item.name
            counter = 1
            while destination.exists():
                destination = destination_dir / f"{item.stem}_{counter}{item.suffix}"
                counter += 1
            if safe_rename(item, destination):
                sorted_count += 1
            else:
                failed += 1
        except Exception:
            logging.exception("Could not sort %s", item.name)
            failed += 1

    q.put(("bar_set", 1))
    q.put(("bar_text", "100%"))
    return result(sorted_count, "file", "sorted", failed)


def duplicate_finder():
    mode = cfg["duplicate_mode"]
    files = sorted(list_files(target_folder), key=lambda t: t[0].name.lower())
    sizes = Counter(s for _, s in files)
    total = sum(s for _, s in files) or 1
    done = 0
    seen = {}
    removed = 0
    failed = 0
    bar_start()

    for item, item_size in files:
        done += item_size
        progress("Finding duplicates...", done, total)

        if sizes[item_size] < 2 or item_size == 0:
            continue
        try:
            file_hash = get_hash(item)
        except OSError:
            logging.exception("Could not read %s.", item.name)
            failed += 1
            continue

        if file_hash not in seen:
            seen[file_hash] = item
            continue
        try:
            if is_copy(seen[file_hash]) and not is_copy(item):
                ok = remove_duplicate(seen[file_hash], mode)
                seen[file_hash] = item
            else:
                ok = remove_duplicate(item, mode)
            if ok:
                removed += 1
            else:
                failed += 1
        except Exception:
            logging.exception("Could not remove duplicate %s.", item.name)
            failed += 1

    q.put(("bar_set", 1))
    q.put(("bar_text", "100%"))
    if removed == 0 and failed == 0:
        old = mode == "Moved to a folder" and duplicates.exists() and any(duplicates.iterdir())
        return mark() + ("No new duplicates found." if old else "No duplicates found.")
    verb = "moved" if mode == "Moved to a folder" else "removed"
    return result(removed, "duplicate", verb, failed)


def rename():
    if check == 0:
        return "✗ Custom name is not valid."
    choice = cfg["pattern"]
    renameby = cfg["renameby"]
    custom = cfg["custom"]

    files = sorted(list_files(target_folder), key=lambda t: t[0].name.lower())
    if not files:
        return mark() + "No files to rename."
    total = sum(s for _, s in files) or 1
    done = 0
    width = len(str(len(files)))
    renamed = 0
    failed = 0
    bar_start()

    for number, (item, item_size) in enumerate(files, start=1):
        done += item_size
        progress("Renaming files...", done, total)
        try:
            number_text = str(number).zfill(width)
            if choice == "date + number":
                file_time = get_file_date(item, renameby)
                base = f"{file_time.year}-{file_time.month:02d}-{file_time.day:02d}_{number_text}"
            elif choice == "original name + number":
                base = f"{item.stem}_{number_text}"
            elif choice == "custom name + number":
                base = f"{custom}_{number_text}"
            else:
                continue

            destination = target_folder / f"{base}{item.suffix}"
            if destination == item:
                continue
            counter = 0
            while destination.exists():
                counter += 1
                destination = target_folder / f"{base}_{counter}{item.suffix}"
            if safe_rename(item, destination):
                renamed += 1
            else:
                failed += 1
        except Exception:
            logging.exception("Could not rename %s", item.name)
            failed += 1

    q.put(("bar_set", 1))
    q.put(("bar_text", "100%"))
    return result(renamed, "file", "renamed", failed)
    
COPY_RE = re.compile(r"(?: \(\d+\)| - (?:copy|kópia)(?: \(\d+\))?)$", re.IGNORECASE)

def is_copy(file):
    return bool(COPY_RE.search(file.stem))
WM_CORNERS = ["Top Right", "Top Left", "Bottom Right", "Bottom Left", "Centre"]
wm_cache = {"key": None, "img": None}

def wm_ready():
    p = setting_get("watermark_path")
    return bool(p) and Path(p).is_file()

def watermark_pick():
    chosen = filedialog.askopenfilename(title="Choose a watermark image", filetypes=[("Images", "*.png *.webp *.jpg *.jpeg"), ("All files", "*.*")])
    if not chosen:
        return False
    setting_set("watermark_path", chosen)
    return True

def wm_stamp():
    p = setting_get("watermark_path")
    if not p:
        return None
    try:
        key = (p, Path(p).stat().st_mtime_ns)
    except OSError:
        return None
    if wm_cache["key"] != key:
        try:
            wm_cache["img"] = Image.open(p).convert("RGBA")
        except Exception:
            logging.exception("Could not open the watermark image.")
            wm_cache["img"] = None
        wm_cache["key"] = key
    return wm_cache["img"]

def watermark_apply(img, stamp, corner, percent):
    img = img.convert("RGBA")
    w, h = img.size
    mw = max(1, round(w * percent / 100))
    mh = max(1, round(stamp.height * mw / stamp.width))
    small = stamp.resize((mw, mh), Image.LANCZOS)
    m = round(min(w, h) * 0.02)
    if corner == "Top Left":
        pos = (m, m)
    elif corner == "Top Right":
        pos = (w - mw - m, m)
    elif corner == "Bottom Left":
        pos = (m, h - mh - m)
    elif corner == "Bottom Right":
        pos = (w - mw - m, h - mh - m)
    else:
        pos = ((w - mw) // 2, (h - mh) // 2)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    layer.paste(small, (max(pos[0], 0), max(pos[1], 0)))
    return Image.alpha_composite(img, layer)

def ed_watermark(img, st):
    if not st["wm_on"]:
        return img
    stamp = wm_stamp()
    if stamp is None:
        return img
    return watermark_apply(img, stamp, st["wm_corner"], st["wm_size"]).convert("RGB")

PROTECTED_NAMES = {"desktop.ini", "thumbs.db", ".ds_store", "ntuser.dat", "pagefile.sys", "hiberfil.sys", "swapfile.sys"}
PROTECTED_SUFFIXES = {".sys", ".dll", ".drv", ".ini", ".exe", ".msi", ".lnk", ".bat", ".cmd", ".reg"}

def is_protected_item(item):
    name = item.name.lower()
    if name in PROTECTED_NAMES or item.suffix.lower() in PROTECTED_SUFFIXES:
        return True
    if name.startswith(".") or name.startswith("$"):
        return True
    try:
        if item.is_symlink():
            return True
        attributes = item.lstat().st_file_attributes
        if attributes & (0x2 | 0x4 | 0x1000 | 0x40000 | 0x400000):
            return True
    except (AttributeError, OSError): pass
    return False

def list_files(folder):
    files = []
    for f in folder.iterdir():
        try:
            if f.is_file() and not is_protected_item(f) and f not in preview_removed:
                files.append((f, f.stat().st_size))
        except OSError:
            continue
    return files

def is_dangerous(folder):
    folder = folder.resolve()
    home = Path.home().resolve()
    system_root = Path(os.environ.get("SystemDrive", "C:") + "\\")
    if folder == system_root or folder == home or folder == home.parent:
        return True
    for name in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "ProgramData", "APPDATA", "LOCALAPPDATA"):
        value = os.environ.get(name)
        if value:
            blocked = Path(value).resolve()
            if folder == blocked or blocked in folder.parents:
                return True
    for part in folder.parts:
        if part.lower() in ("appdata", "$recycle.bin", "system volume information"):
            return True
    return False


def pick_folder():
    global target_folder
    global duplicates
    global sorted_dir

    chosen = filedialog.askdirectory()
    if not chosen:
        return
    try:
        dangerous = is_dangerous(Path(chosen))
    except OSError:
        messagebox.showwarning("Specorde", "Can't access that folder. Please pick another folder.")
        return
    if dangerous:
        messagebox.showwarning("Specorde", "This folder is protected and can't be organized. Please pick another folder.")
        return
    target_folder = Path(chosen)
    folder_browser.configure(text="Change folder")
    label_font = ctk.CTkFont(family="Bahnschrift Light Condensed", size=14)
    prefix = "Folder: "
    shown_name = target_folder.name or str(target_folder)
    if label_font.measure(prefix + shown_name) > 128:
        while shown_name and label_font.measure(prefix + shown_name + "...") > 128:
            shown_name = shown_name[:-1]
        shown_name = shown_name.rstrip() + "..."
    folder_chosen.configure(text=prefix + shown_name)
    frames_loaded = False
    sorted_dir = Path(target_folder/"sorted_specorde")
    duplicates = Path(target_folder/"duplicates_specorde")
    q.put(("status", "Folder ready!"))
    q.put(("status_reset", None))
    q.put(("unlock", None))
    if currently_open == 3: pictures_open()
    

allowed_characters = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z", "_", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
def get_hash(filepath:  Path):
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def execute():
    global journal_name, preview_count
    q.put(("lock", None))
    q.put(("summary_clear", None))
    started = time.perf_counter()
    preview_count = 0
    preview_removed.clear()
    final_status = "Preview done! See log..." if dry_run else "Done!"
    had_errors = False
    try:
        journal_name = journal_path / f"run_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')}.jsonl"
        if not dry_run:
            journal_path.mkdir(parents=True, exist_ok=True)
            with open(journal_name, "x", encoding="utf-8") as f:
                f.write(json.dumps({"folder": str(target_folder)}) + "\n")

        logging.info("=" * 60)
        logging.info("RUN%s  %s  folder: %s", "  [PREVIEW]" if dry_run else "", datetime.now().strftime("%Y-%m-%d %H:%M"), target_folder)

        steps = []
        if cfg["find"]:
            logging.info("  find duplicates -> %s", cfg["duplicate_mode"].lower())
            steps.append(("Find duplicates", duplicate_finder))
        if cfg["rename"]:
            detail = cfg["pattern"]
            if detail == "date + number":
                detail += f", by {cfg['renameby'].lower()}"
            elif detail == "custom name + number":
                detail += f", name '{cfg['custom']}'"
            logging.info("  rename -> %s", detail)
            steps.append(("Rename", rename))
        if cfg["sort"]:
            logging.info("  sort -> by %s, %s", cfg["sortby"].lower(), cfg["structure"])
            steps.append(("Sort", sort))

        q.put(("bar_show", None))
        q.put(("bar_text_show", None))
        for label, step in steps:
            step_started = time.perf_counter()
            try:
                line = step()
            except Exception:
                logging.exception("%s failed", label)
                line = f"✗ {label} failed (see log)."
            if line.startswith("✗"):
                had_errors = True
            q.put(("summary_add", line))
            logging.info("%s: %s  (%.1f s)", label, line[2:], time.perf_counter() - step_started)
        if had_errors:
            final_status = "Done with errors. See log..."
    except Exception:
        logging.exception("Error trying to execute.")
        final_status = "Something went wrong. See log..."
    finally:
        if not dry_run:
            try:
                with open(journal_name, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                if len(lines) <=1:
                    journal_name.unlink()
                    logging.info("This run had no changes. No journal saved.")
            except OSError: pass
        logging.info("Run finished in %.1f s", time.perf_counter() - started)
        q.put(("bar_text_destroy", None))
        q.put(("bar_destroy", None))
        q.put(("status", final_status))
        q.put(("status_reset", None))
        q.put(("summary_hide_later", None))
        q.put(("unlock", None))

restore_stats = {"done": 0, "failed": 0, "missing": 0, "total": 1}

def restore_tick():
    restore_stats["done"] += 1
    progress("Restoring...", restore_stats["done"], restore_stats["total"])
    return 1

def restore_line(count, failed, missing=0):
    if not count and not failed and not missing:
        return "○ Nothing to restore."
    n = f"{count} change" + ("" if count == 1 else "s")
    text = f"{n} undone"
    extra = []
    if missing:
        extra.append(f"{missing} missing")
    if failed:
        extra.append(f"{failed} failed")
    if extra:
        text += " (" + ", ".join(extra) + ")"
    return ("✗ " if failed or missing else "✓ ") + text + "."

def restore_duplicates(source, dest):
    moved = 0
    if source.exists():
        q.put(("status", "Restoring duplicates..."))        
        for item in list(source.iterdir()):
                counter = 0
                destination = dest/item.name
                while destination.exists():
                    counter += 1
                    destination = Path(f"{dest}/{item.stem}_restored_{counter}{item.suffix}")
                try:
                    item.rename(destination)
                    moved += restore_tick()
                except OSError:
                    logging.error("Could not restore %s.", item.name)
                    restore_stats["failed"] += 1
    return moved

def restore_sorted(source, dest):
    moved = 0
    for year in list(source.iterdir()):
        if not year.is_dir():
            continue
        for month in list(year.iterdir()):
            if not month.is_dir():
                continue
            for month_sub in list(month.iterdir()):
                if month_sub.is_file():
                    counter = 0
                    destination = dest/month_sub.name
                    while destination.exists():
                        counter += 1
                        destination = Path(f"{dest}/{month_sub.stem}_restored_{counter}{month_sub.suffix}")
                    try:
                        month_sub.rename(destination)
                        moved += restore_tick()
                    except OSError:
                        logging.error("Could not restore %s.", month_sub.name)
                        restore_stats["failed"] += 1
                elif month_sub.name.isdigit():
                    for item in list(month_sub.iterdir()):
                        if not item.is_file(): continue
                        counter = 0
                        destination = dest/item.name
                        while destination.exists():
                            counter += 1
                            destination = Path(f"{dest}/{item.stem}_restored_{counter}{item.suffix}")
                        try:
                            item.rename(destination)
                            moved += restore_tick()
                        except OSError:
                            logging.error("Could not restore %s.", item.name)
                            restore_stats["failed"] += 1
                    try:
                        month_sub.rmdir()
                    except OSError: pass
            try:
                month.rmdir()
            except OSError: pass
        try:
            year.rmdir()
        except OSError: pass
    return moved

def remove_empty_dirs(root):
    if not root.is_dir():
        return
    for folder, _, _ in os.walk(root, topdown=False):
        try:
            os.rmdir(folder)
        except OSError:
            pass

def prune_empty_parents(parent):
    while parent != target_folder and target_folder in parent.parents:
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent

def restore_skip():
    restore_stats["done"] += 1
    progress("Restoring...", restore_stats["done"], restore_stats["total"])
    return 0

def restore_from_journal(entries):
    moved = 0
    for entry in reversed(entries):
        try:
            moved_to = Path(entry["to"])
            original = Path(entry["from"])
        except (KeyError, TypeError):
            logging.error("Bad journal entry: %r", entry)
            restore_stats["failed"] += 1
            continue

        try:
            moved_to.resolve().relative_to(target_folder.resolve())
            original.resolve().relative_to(target_folder.resolve())
        except (ValueError, OSError, RuntimeError):
            logging.error("Journal contains a path outside the selected folder: %r.", entry)
            restore_stats["failed"] += 1
            continue

        if not moved_to.exists():
            if not original.exists():
                logging.warning("Missing, nothing to restore: %s", moved_to)
                restore_stats["missing"] += 1
            restore_skip()
            prune_empty_parents(moved_to.parent)
            continue

        try:
            counter = 0
            destination = original
            while destination.exists():
                counter += 1
                destination = Path(f"{original.parent}/{original.stem}_restored_{counter}{original.suffix}")
            moved_to.rename(destination)
            moved += restore_tick()
            prune_empty_parents(moved_to.parent)
        except OSError:
            logging.error("Could not restore %s.", moved_to.name)
            restore_stats["failed"] += 1
    return moved

def start_restoring():
    global target_folder
    entries = []
    parse_errors = 0
    moved = 0
    duplicates_moved = 0
    target_folder_remove = 0
    if "target_folder" not in globals():
        q.put(("status", "You must pick a folder."))
        q.put(("status_reset", None))
        return
    q.put(("lock", None))
    try:
        if not target_folder.is_dir():
            q.put(("status", "Your chosen folder no longer exists."))
            q.put(("status_reset", None))
            return

        journal_file = find_last_run()
        if journal_file is None:
            if not duplicates.exists() and not sorted_dir.exists():
                if target_folder.name not in ("sorted_specorde", "duplicates_specorde"):
                    q.put(("status", "Nothing to restore..."))
                    q.put(("status_reset", None))
                    return
        else:
            q.put(("status", "Restoring..."))
            with open(journal_file, "r", encoding="utf-8") as f:
                f.readline()
                for line_number, line in enumerate(f, start=2):
                    try:
                        item = json.loads(line)
                        entries.append(item)
                    except json.JSONDecodeError:
                        logging.exception("Invalid journal entry on line %d.", line_number)
                        parse_errors += 1

        logging.info("RESTORE  folder: %s", target_folder)
        restore_stats.update(done=0, failed=0, missing=0, total=1)
        restore_stats["failed"] += parse_errors
        if target_folder.name in ("sorted_specorde", "duplicates_specorde"):
            restore_stats["total"] = max(sum(1 for p in target_folder.rglob("*") if p.is_file()), 1)
        else:
            restore_stats["total"] = max(len(entries) or sum(1 for d in (sorted_dir, duplicates) if d.exists() for p in d.rglob("*") if p.is_file()), 1)
        q.put(("summary_clear", None))
        q.put(("bar_show", None))
        q.put(("bar_text_show", None))

        if target_folder.name == "sorted_specorde":
            moved = restore_sorted(target_folder, target_folder.parent)
            target_folder_remove = 1
            if moved:
                q.put(("status", "Everything back in its place!"))
            else:
                q.put(("status", "Nothing to restore..."))
            q.put(("status_reset", None))

        elif target_folder.name == "duplicates_specorde":
            moved = restore_duplicates(target_folder, target_folder.parent)
            target_folder_remove = 1
            if moved:
                q.put(("status", "Everything back in its place!"))
            else:
                q.put(("status", "Nothing to restore..."))
            q.put(("status_reset", None))

        else:
            moved = restore_from_journal(entries)
            if journal_file is None:
                if sorted_dir.exists():
                    moved += restore_sorted(sorted_dir, target_folder)
                    try:
                        sorted_dir.rmdir()
                    except OSError: pass
                duplicates_moved = restore_duplicates(duplicates, target_folder)
            remove_empty_dirs(sorted_dir)
            remove_empty_dirs(duplicates)
            if moved or duplicates_moved:
                q.put(("status", "Restored, some files were missing." if restore_stats["missing"] else "Everything back in its place!"))
            elif restore_stats["missing"]:
                q.put(("status", "Restore incomplete: files are missing."))
            else:
                q.put(("status", "Nothing to restore..."))
            q.put(("status_reset", None))

        total_moved = moved + duplicates_moved
        failed = restore_stats["failed"]
        logging.info("Restore finished: %d undone, %d failed.", total_moved, failed)
        q.put(("bar_set", 1))
        q.put(("bar_text", "100%"))
        if failed:
            q.put(("status", "Restored with errors. See log."))
            q.put(("status_reset", None))
        q.put(("summary_add", restore_line(total_moved, failed, restore_stats["missing"])))
        q.put(("summary_hide_later", None))

        if journal_file is not None and failed - parse_errors == 0:
            try:
                journal_file.rename(journal_file.with_suffix(".used"))
            except OSError:
                logging.exception("Could not mark journal as used; keeping it for recovery")

        if target_folder_remove == 1:
            try:
                target_folder.rmdir()
                del target_folder
                q.put(("folder_reset", None))
            except OSError: pass
    except Exception:
        logging.exception("Restore failed.")
        q.put(("status", "Restore failed. See log."))
        q.put(("status_reset", None))
    finally:
        q.put(("bar_text_destroy", None))
        q.put(("bar_destroy", None))
        q.put(("unlock", None))

def restore_click():
    if "target_folder" not in globals():
        q.put(("status", "You must pick a folder."))
        q.put(("status_reset", None))
        return
    if not messagebox.askyesno("Specorde", f"Put the files in '{target_folder.name or target_folder}' back where they were before the last run?\n\nFiles sent to the Recycle Bin can't be restored by Specorde.\n\nContinue?"):
        return
    lock_ui()
    start_execute(start_restoring) 

def middle_reset():
    global header
    ed_focus(False)
    try:
        for widget in header.winfo_children():
            widget.grid_forget()
    except Exception: pass
    for widget in middle.winfo_children():
        widget.grid_forget()
pic_suffixes = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}
if heif_ok:
    pic_suffixes |= heif_suffixes
if raw_ok:
    pic_suffixes |= raw_suffixes
view_w = 652
view_h_base = 474
grid_left = 24
grid_gap_x = 12
grid_top = 28
grid_gap_y = 24
grid_buffer_rows = 2
cell_color = "#1f2029"
card_edge = "#2c3043"
dim_color = "#20222e"
hover_color = "#1f6aa5"
wheel_speed = 0.35
wheel_max_step = 60
stack_limit = 3
stack_peek = 9
stack_inset = 7
dbl_ms = 250
ungrouped_first = True
all_cameras = "All cameras"
unknown_camera = "Unknown camera"

pending_pics = []
pic_cells = {}
cell_info = {}
pic_images = {}
pic_badges = {}
pics_folder = None
pics_stamp = None
pic_total_h = 0
grid_job = None
grid_scale = 1.0

def ui_scale():
    try:
        s = scale_probe.winfo_reqwidth() / 1000
    except Exception:
        return 1.0
    return s if 0.3 < s < 5 else 1.0

def grid_geometry():
    s = ui_scale()
    w, h, per_row = sizes[size]
    return {
        "s": s,
        "w": w * s,
        "h": h * s,
        "per_row": per_row,
        "left": grid_left * s,
        "gap_x": grid_gap_x * s,
        "top": grid_top * s,
        "pitch": (h + grid_gap_y) * s,
        "slot0": (grid_top - grid_gap_y / 2) * s,
    }

def grid_view_h(geo):
    h = pic_canvas.winfo_height()
    return h if h > 1 else view_h_base * geo["s"]

def apply_flip(img, flip):
    if flip == 3:
        return img.rotate(180)
    if flip in (5, 6) and img.width >= img.height:
        return img.rotate(90 if flip == 5 else -90, expand=True)
    return img

def raw_open(file, need=0):
    with rawpy.imread(str(file)) as raw:
        flip = raw.sizes.flip
        img = None
        try:
            thumb = raw.extract_thumb()
            if thumb.format == rawpy.ThumbFormat.JPEG:
                img = Image.open(io.BytesIO(thumb.data))
            elif thumb.format == rawpy.ThumbFormat.BITMAP:
                img = Image.fromarray(thumb.data)
        except Exception:
            img = None
        if img is not None and max(img.size) < need:
            img.close()
            img = None
        if img is None:
            return Image.fromarray(raw.postprocess(half_size=True, use_camera_wb=True)), 0
    if img.getexif().get(274, 1) != 1:
        return img, 0
    return img, flip

sharp_side = 1024
sharp_tiles = 6
sharp_top_share = 0.25
LAPLACE = ImageFilter.Kernel((3, 3), (0, 1, 0, 1, -4, 1, 0, 1, 0), scale=4, offset=128)
sharp_cache = {}
sharp_lock = threading.Lock()
suggest_token = 0
suggest_tags = {}

def sharp_measure(file):
    img = load_image(file, (sharp_side, sharp_side), need=sharp_side, mode="L")
    img.thumbnail((sharp_side, sharp_side), Image.BILINEAR)
    w, h = img.size
    lap = img.filter(LAPLACE).crop((2, 2, w - 2, h - 2))
    lw, lh = lap.size
    n = sharp_tiles if min(lw, lh) >= sharp_tiles * 8 else 1
    scores = []
    for r in range(n):
        for c in range(n):
            tile = lap.crop((c * lw // n, r * lh // n, (c + 1) * lw // n, (r + 1) * lh // n))
            scores.append(ImageStat.Stat(tile).var[0])
    scores.sort(reverse=True)
    top = max(1, round(len(scores) * sharp_top_share))
    return sum(scores[:top]) / top

def sharp_get(file):
    try:
        st = file.stat()
    except OSError:
        return None
    key = (str(file), st.st_size, st.st_mtime_ns)
    with sharp_lock:
        if key in sharp_cache:
            return sharp_cache[key]
    try:
        score = sharp_measure(file)
    except Exception:
        logging.exception("Could not measure sharpness of %s", file.name)
        score = None
    with sharp_lock:
        sharp_cache[key] = score
    return score
    
def load_image(file, target, need=0, mode="RGB"):
    flip = 0
    if file.suffix.lower() in raw_suffixes:
        source, flip = raw_open(file, need)
    else:
        source = Image.open(file)
    try:
        source.draft(mode, target)
        out = ImageOps.exif_transpose(source).convert(mode)
    finally:
        source.close()
    if flip:
        out = apply_flip(out, flip)
    return out

thumb_cache = OrderedDict()
thumb_cache_max = 600
thumb_failed = set()
thumb_pending = set()
thumb_requests = queue.LifoQueue()
thumb_results = queue.Queue()
thumb_workers = 3
thumb_per_tick = 6
thumbs_dir = path / "thumbs"
thumbs_limit = 600 * 1024 * 1024
thumb_base_side = 640

try:
    thumbs_dir.mkdir(exist_ok=True)
except OSError:
    logging.warning("Could not create the thumbnail folder.")

def thumb_base_path(file):
    try:
        st = file.stat()
    except OSError:
        return None
    key = f"{file}|{st.st_size}|{st.st_mtime_ns}"
    return thumbs_dir / f"{hashlib.sha1(key.encode('utf-8')).hexdigest()}.jpg"

def thumb_base_save(img, target):
    tmp = target.with_name(f"{target.stem}.{threading.get_ident()}.tmp")
    try:
        img.save(tmp, "JPEG", quality=85)
        os.replace(tmp, target)
    except OSError:
        logging.warning("Could not save a cached thumbnail.")
        try:
            tmp.unlink()
        except OSError:
            pass

def thumb_base(file):
    cached = thumb_base_path(file)
    if cached is not None and cached.exists():
        try:
            with Image.open(cached) as img:
                out = img.convert("RGB")
            try:
                os.utime(cached)
            except OSError:
                pass
            return out
        except Exception:
            logging.warning("Cached thumbnail unreadable, rebuilding: %s", file.name)
    img = load_image(file, (thumb_base_side * 2, thumb_base_side * 2))
    img.thumbnail((thumb_base_side, thumb_base_side), Image.BILINEAR)
    if cached is not None:
        thumb_base_save(img, cached)
    return img

def thumbs_trim():
    try:
        entries = []
        total = 0
        for f in thumbs_dir.glob("*.jpg"):
            st = f.stat()
            entries.append((st.st_mtime, st.st_size, f))
            total += st.st_size
        if total <= thumbs_limit:
            return
        entries.sort()
        for mtime, size_bytes, f in entries:
            if total <= thumbs_limit * 0.8:
                break
            f.unlink()
            total -= size_bytes
    except OSError:
        logging.exception("Could not trim the thumbnail cache.")

def thumb_key(file, w, h, dim=0):
    return (str(file), w, h, dim)

def thumb_load(file, w, h, dim=0):
    img = ImageOps.fit(thumb_base(file), (w, h), Image.BILINEAR)
    if dim:
        img = Image.blend(img, Image.new("RGB", img.size, dim_color), 0.5)
    return img

def card_path(ck):
    idx, layer = ck
    if idx < len(cards) and layer < len(cards[idx]):
        return cards[idx][layer]
    return None

def draw_thumb(ck, photo):
    if ck in pic_images or ck not in pic_cells:
        return
    x1, y1, x2, y2 = pic_canvas.coords(pic_cells[ck])
    image_id = pic_canvas.create_image(x1, y1, image=photo, anchor="nw")
    pic_images[ck] = image_id
    idx, layer = ck
    if layer > 0 and (idx, layer - 1) in pic_cells:
        pic_canvas.tag_lower(image_id, pic_cells[(idx, layer - 1)])
    for item_id in pic_badges.get(idx, ()):
        pic_canvas.tag_raise(item_id)

def thumb_request(ck):
    file = card_path(ck)
    info = cell_info.get(ck)
    if file is None or info is None:
        return
    w, h, dim = info
    key = thumb_key(file, w, h, dim)
    if key in thumb_failed:
        return
    photo = thumb_cache.get(key)
    if photo is not None:
        thumb_cache.move_to_end(key)
        draw_thumb(ck, photo)
        return
    if key in thumb_pending:
        return
    thumb_pending.add(key)
    thumb_requests.put((ck, file, w, h, dim))

def thumb_worker():
    while True:
        ck, file, w, h, dim = thumb_requests.get()
        key = thumb_key(file, w, h, dim)
        if ck not in pic_cells:
            thumb_results.put((key, ck, None, False))
            continue
        try:
            thumb_results.put((key, ck, thumb_load(file, w, h, dim), False))
        except Exception:
            logging.exception("Could not make thumbnail for %s", file)
            thumb_results.put((key, ck, None, True))

def start_thumb_workers():
    for _ in range(thumb_workers):
        threading.Thread(target=thumb_worker, daemon=True).start()
threading.Thread(target=thumbs_trim, daemon=True).start()
def thumb_poll():
    try:
        for _ in range(thumb_per_tick):
            key, ck, img, failed = thumb_results.get_nowait()
            thumb_pending.discard(key)
            if failed:
                thumb_failed.add(key)
                continue
            if img is not None:
                thumb_cache[key] = ImageTk.PhotoImage(img)
                while len(thumb_cache) > thumb_cache_max:
                    thumb_cache.popitem(last=False)
            for cell in [c for c in pic_cells if c not in pic_images]:
                if str(card_path(cell)) == key[0]:
                    thumb_request(cell)
    except queue.Empty:
        pass
    except Exception:
        logging.exception("thumb_poll failed")
    pic_canvas.after(20, thumb_poll)

photo_epoch = datetime(1970, 1, 1)
photo_cache_file = path / "photo_cache_v3.json"
photo_cache_max = 20000
photo_info = {}
scan_token = 0
scan_total = 0
scan_done = 0
scan_active = False
scan_started = 0.0
scan_order = []
scan_stats = {"cached": 0, "failed": 0, "new": 0}
scan_requests = queue.Queue()
scan_results = queue.Queue()
scan_workers = 3
scan_per_tick = 200
cache_lock = threading.Lock()
copy_hidden = set()
copies_active = False
copy_results = queue.Queue()

def cache_load():
    try:
        with open(photo_cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError):
        logging.warning("Photo cache unreadable, starting fresh.")
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, list) and len(v) == 5}

photo_cache = cache_load()

def cache_save(snapshot):
    tmp = photo_cache_file.with_suffix(".tmp")
    with cache_lock:
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(snapshot, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, photo_cache_file)
        except OSError:
            logging.exception("Could not save the photo cache.")

def exif_text(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    return str(value).strip("\x00 ").strip()

FEAT_GRAY = 256
FEAT_LEN = FEAT_GRAY + 192
GRAY_W = [1.0 if 3 <= i // 16 <= 12 and 3 <= i % 16 <= 12 else 0.3 for i in range(256)]
COL_W = [1.0 if 2 <= i // 8 <= 5 and 2 <= i % 8 <= 5 else 0.3 for i in range(64)]
GRAY_SUM = sum(GRAY_W)

def image_feature(img):
    gray = img.convert("L").resize((16, 16), Image.BOX)
    colour = img.resize((8, 8), Image.BOX)
    return gray.tobytes().hex() + colour.tobytes().hex()

def decode_feature(text):
    try:
        data = bytes.fromhex(text)
    except (TypeError, ValueError):
        return None
    return data if len(data) == FEAT_LEN else None

def trimmed_mean(pairs, keep):
    pairs.sort()
    limit = sum(w for _, w in pairs) * keep
    used = 0.0
    total = 0.0
    for d, w in pairs:
        take = min(w, limit - used)
        if take <= 0:
            break
        total += d * take
        used += take
    return total / used if used else 0.0

def feature_distance(a, b, keep):
    off = sum(w * (a[i] - b[i]) for i, w in enumerate(GRAY_W)) / GRAY_SUM
    gray_pairs = [(abs(a[i] - b[i] - off), w) for i, w in enumerate(GRAY_W)]
    struct_d = trimmed_mean(gray_pairs, keep)
    col_pairs = []
    for i, w in enumerate(COL_W):
        j = FEAT_GRAY + i * 3
        col_pairs.append(((abs(a[j] - b[j]) + abs(a[j + 1] - b[j + 1]) + abs(a[j + 2] - b[j + 2])) / 3, w))
    colour_d = trimmed_mean(col_pairs, 1.0 if keep >= 1.0 else 0.9)
    return struct_d, colour_d, abs(off)

def exif_from_pillow(exif):
    try:
        ifd = exif.get_ifd(0x8769)
    except Exception:
        ifd = {}
    date = exif_text(ifd.get(36867) or ifd.get(36868) or exif.get(36867))
    return date, exif_text(ifd.get(37521)), exif_text(exif.get(271)), exif_text(exif.get(272))

def exif_from_exifread(file):
    if not exifread_ok:
        return "", "", "", ""
    try:
        with open(file, "rb") as f:
            tags = exifread.process_file(f, details=False)
    except Exception:
        logging.warning("exifread could not read %s", file.name)
        return "", "", "", ""

    def get(name):
        return exif_text(tags.get(name))

    date = get("EXIF DateTimeOriginal") or get("EXIF DateTimeDigitized")
    return date, get("EXIF SubSecTimeOriginal"), get("Image Make"), get("Image Model")

def exif_from_raw_preview(file):
    if not raw_ok:
        return "", "", "", ""
    try:
        with rawpy.imread(str(file)) as raw:
            thumb = raw.extract_thumb()
            if thumb.format != rawpy.ThumbFormat.JPEG:
                return "", "", "", ""
            with Image.open(io.BytesIO(thumb.data)) as img:
                return exif_from_pillow(img.getexif())
    except Exception:
        return "", "", "", ""

def read_photo_info(file):
    if file.suffix.lower() in raw_suffixes:
        date, subsec, make, model = exif_from_exifread(file)
        if not date:
            date, subsec, make2, model2 = exif_from_raw_preview(file)
            make = make or make2
            model = model or model2
    else:
        with Image.open(file) as img:
            date, subsec, make, model = exif_from_pillow(img.getexif())
    stamp = None
    if date:
        moment = parse_exif_date(date)
        if moment:
            stamp = (moment - photo_epoch).total_seconds()
            digits = "".join(ch for ch in subsec if ch.isdigit())
            if digits:
                stamp += float("0." + digits)
    if model:
        first = make.split()[0].lower() if make else ""
        if not first or model.lower().startswith(first):
            camera = model
        else:
            camera = f"{make} {model}"
    else:
        camera = make or None
    feature = image_feature(load_image(file, (160, 160)))
    return stamp, camera, feature

def scan_worker():
    while True:
        token, file = scan_requests.get()
        if token != scan_token:
            continue
        try:
            st = file.stat()
            entry = photo_cache.get(str(file))
            if entry and entry[0] == st.st_size and entry[1] == st.st_mtime_ns:
                scan_results.put((token, file, st.st_size, st.st_mtime_ns, entry[2], entry[3], entry[4], True, False))
                continue
            stamp, camera, dhash = read_photo_info(file)
            scan_results.put((token, file, st.st_size, st.st_mtime_ns, stamp, camera, dhash, False, False))
        except Image.UnidentifiedImageError:
            logging.warning("Not a readable picture, skipping: %s", file.name)
            scan_results.put((token, file, 0, 0, None, None, None, False, True))
        except Exception:
            logging.exception("Could not read info of %s", file)
            scan_results.put((token, file, 0, 0, None, None, None, False, True))

def start_scan_workers():
    for _ in range(scan_workers):
        threading.Thread(target=scan_worker, daemon=True).start()

def copies_worker(token, snapshot):
    buckets = {}
    for file, dhash in snapshot:
        try:
            size_bytes = file.stat().st_size
        except OSError:
            continue
        buckets.setdefault((size_bytes, dhash), []).append(file)
    hidden = set()
    for files in buckets.values():
        if len(files) < 2:
            continue
        seen_digests = set()
        for file in sorted(files, key=lambda f: (is_copy(f), f.name.lower())):
            try:
                digest = get_hash(file)
            except OSError:
                continue
            if digest in seen_digests:
                hidden.add(file)
            else:
                seen_digests.add(digest)
    copy_results.put((token, hidden))

def scan_finish():
    global scan_active
    global copies_active
    scan_active = False
    try:
        elapsed = time.perf_counter() - scan_started
        with_time = sum(1 for v in photo_info.values() if v[0] is not None)
        with_camera = sum(1 for v in photo_info.values() if v[1])
        cameras = Counter(v[1] for v in photo_info.values() if v[1])
        logging.info("Scanned %d photos in %.1f s: %d with time, %d with camera, %d without time, %d from cache, %d unreadable.", scan_total, elapsed, with_time, with_camera, scan_total - with_time, scan_stats["cached"], scan_stats["failed"])
        for name, count in cameras.most_common():
            logging.info("  camera %s: %d photos", name, count)
        extra = len(photo_cache) - photo_cache_max
        if extra > 0:
            for key in list(photo_cache)[:extra]:
                del photo_cache[key]
        if scan_stats["new"]:
            threading.Thread(target=cache_save, args=(dict(photo_cache),), daemon=True).start()
    except Exception:
        logging.exception("Could not finish the scan.")
    snapshot = [(f, v[2]) for f, v in photo_info.items() if v[2] is not None]
    copies_active = True
    culler_loading.configure(text="Checking for copies...")
    threading.Thread(target=copies_worker, args=(scan_token, snapshot), daemon=True).start()

def scan_complete():
    global copies_active
    copies_active = False
    cameras_setup()
    state_prune()
    groups_build()
    groups_log()
    grid_clear()
    grid_update_region(grid_geometry())
    pic_canvas.yview_moveto(0)
    if currently_open == 3 and pics_view == "grid":
        header_show()
        empty_update()
    if culler_loading.winfo_manager():
        culler_loading.grid_forget()
        overview_frame.grid(row=1, column=0, sticky="ew")
        cutesy_bar.grid(row=10, column=0, sticky="sew")
        bottom_bar_update()
        schedule_refresh()

def scan_poll():
    global scan_done
    global copy_hidden
    try:
        if scan_active:
            for _ in range(scan_per_tick):
                try:
                    token, file, size_bytes, mtime, stamp, camera, dhash, cached, failed = scan_results.get_nowait()
                except queue.Empty:
                    break
                if token != scan_token:
                    continue
                scan_done += 1
                photo_info[file] = (stamp, camera, dhash, mtime / 1e9, bool(failed))
                if failed:
                    scan_stats["failed"] += 1
                elif cached:
                    scan_stats["cached"] += 1
                else:
                    photo_cache[str(file)] = [size_bytes, mtime, stamp, camera, dhash]
                    scan_stats["new"] += 1
            text = f"Reading photos {scan_done}/{scan_total}"
            if culler_loading.cget("text") != text:
                culler_loading.configure(text=text)
            if scan_done >= scan_total:
                scan_finish()
        if copies_active:
            try:
                token, hidden = copy_results.get_nowait()
            except queue.Empty:
                token = None
            if token == scan_token:
                copy_hidden = hidden
                scan_complete()
    except Exception:
        logging.exception("scan_poll failed")
    canvas.after(30, scan_poll)

camera_names = []
camera_choice = all_cameras
group_names = ("Tight", "Normal", "Loose")
group_gaps = (3.0, 8.0, 20.0)
group_limits = (6.0, 9.0, 13.0)
group_colours = (9.0, 14.0, 20.0)
group_bright = (18.0, 28.0, 42.0)
group_keep = (0.85, 0.75, 0.65)
strict_struct = 1.5
strict_colour = 4.0
strict_bright = 6.0
strict_gap = 3.0
anchor_limit = 1.7
pick_hard = 1.25
group_level = 1
time_mode = 0
hidden_no_exif = 0
groups = []
cards = []
other_idx = None
open_idx = None
saved_top = 0.0
hover_idx = None
keep_file = path / "keeps.json"
done_file = path / "done.json"

def done_load():
    try:
        with open(done_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return set()
    return {item for item in data if isinstance(item, str)} if isinstance(data, list) else set()

done_set = done_load()

def done_save():
    tmp = done_file.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(sorted(done_set), f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, done_file)
    except OSError:
        logging.exception("Could not save the done list.")

def group_is_done(idx):
    return idx != other_idx and idx < len(groups) and all(str(f) in done_set for f in groups[idx])

def done_set_group(idx, value):
    files = [str(f) for f in groups[idx]]
    if value:
        done_set.update(files)
    else:
        done_set.difference_update(files)
    done_save()


def keep_load():
    try:
        with open(keep_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return set()
    except (OSError, json.JSONDecodeError):
        logging.warning("Keep list unreadable, starting fresh.")
        return set()
    if not isinstance(data, list):
        return set()
    return {item for item in data if isinstance(item, str)}



keep_set = keep_load()

def state_prune():
    folder = str(target_folder)
    for store, save in ((keep_set, keep_save), (done_set, done_save)):
        stale = {k for k in store if os.path.dirname(k) == folder and not os.path.exists(k)}
        if stale:
            store.difference_update(stale)
            save()

def keep_save():
    tmp = keep_file.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(sorted(keep_set), f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, keep_file)
    except OSError:
        logging.exception("Could not save the keep list.")

keep_save_job = None

def keep_save_now():
    global keep_save_job
    keep_save_job = None
    keep_save()

def keep_save_later():
    global keep_save_job
    if keep_save_job is not None:
        canvas.after_cancel(keep_save_job)
    keep_save_job = canvas.after(600, keep_save_now)

def lock_toggle(file):
    key = str(file)
    if key in keep_set:
        keep_set.discard(key)
    else:
        keep_set.add(key)
    keep_save_later()

def camera_of(file):
    info = photo_info.get(file)
    return info[1] if info and info[1] else unknown_camera

def cameras_setup():
    global camera_names
    global camera_choice
    counts = Counter(camera_of(f) for f in scan_order if f not in copy_hidden)
    camera_names = [name for name, count in counts.most_common()]
    camera_choice = all_cameras
    if len(camera_names) > 1:
        culler_camera_menu.configure(values=[all_cameras] + camera_names)
        culler_camera_menu.set(all_cameras)

NAME_DATE_RE = re.compile(r"((?:19|20)\d{2})[-_.]?(\d{2})[-_.]?(\d{2})(?:[-_. T]?(\d{2})[-_.]?(\d{2})[-_.]?(\d{2}))?")

def guess_time(file, stamp, modified):
    if stamp is not None:
        return stamp
    m = NAME_DATE_RE.search(file.stem)
    if m:
        parts = [int(x) if x else 0 for x in m.groups()]
        try:
            return (datetime(*parts) - photo_epoch).total_seconds()
        except ValueError:
            pass
    return (datetime.fromtimestamp(modified) - photo_epoch).total_seconds()

def pair_score(a, b, strict, dt, max_gap):
    keep = 1.0 if strict else group_keep[group_level]
    struct_d, colour_d, bright_d = feature_distance(a, b, keep)
    if strict:
        lim = (strict_struct, strict_colour, strict_bright)
    else:
        lim = (group_limits[group_level], group_colours[group_level], group_bright[group_level])
    pic = max(struct_d / lim[0], colour_d / lim[1], bright_d / lim[2])
    return pic, 0.85 * pic + 0.15 * min(dt / max_gap, 2.0)

def singles_sorted():
    files = [f for f in scan_order if f not in copy_hidden and (camera_choice == all_cameras or camera_of(f) == camera_choice)]
    if all_sort == "Date":
        def stamp(f):
            info = photo_info.get(f)
            return guess_time(f, info[0], info[3]) if info else 0.0
        files.sort(key=lambda f: (stamp(f), f.name.lower()))
    elif all_sort == "Camera":
        files.sort(key=lambda f: (camera_of(f).lower(), f.name.lower()))
    return files

def cards_rebuild():
    global cards, pending_pics
    if pics_mode == "all":
        cards = [[f] for f in singles_sorted()]
    else:
        cards = groups
    pending_pics = [c[0] for c in cards]

def groups_build():
    global groups
    global cards
    global pending_pics
    global open_idx
    global other_idx
    global hidden_no_exif
    gap = group_gaps[group_level]
    by_camera = {}
    extra = []
    hidden_no_exif = 0
    for file in scan_order:
        if file in copy_hidden:
            continue
        info = photo_info.get(file)
        name = camera_of(file) if info else unknown_camera
        if camera_choice != all_cameras and name != camera_choice:
            continue
        if info is None or info[4]:
            extra.append(file)
            continue
        stamp, camera, dhash, modified, failed = info
        feature = decode_feature(dhash) if dhash else None
        if time_mode == 1:
            stamp = guess_time(file, stamp, modified)
        elif stamp is None:
            hidden_no_exif += 1
            extra.append(file)
            continue
        if feature is None:
            extra.append(file)
            continue
        by_camera.setdefault(name, []).append((stamp, file.name.lower(), file, feature))
    built = []
    for name, items in by_camera.items():
        strict = name == unknown_camera
        max_gap = min(gap, strict_gap) if strict else gap
        items.sort(key=lambda t: (t[0], t[1]))
        current = None
        last_stamp = 0.0
        first = None
        recent = []
        for stamp, file_name, file, feature in items:
            joined = False
            dt = stamp - last_stamp
            if current is not None and 0 <= dt <= 2 * max_gap:
                for other in recent:
                    pic, total = pair_score(other, feature, strict, dt, max_gap)
                    if pic <= pick_hard and total <= 1.0:
                        joined = pair_score(first, feature, strict, dt, max_gap)[0] <= anchor_limit
                        break
            if joined:
                current[1].append(file)
                recent = (recent + [feature])[-3:]
            else:
                current = [stamp, [file]]
                built.append(current)
                first = feature
                recent = [feature]
            last_stamp = stamp
    built.sort(key=lambda g: g[0])
    multi = [g[1] for g in built if len(g[1]) >= 2]
    singles = [g[1][0] for g in built if len(g[1]) == 1] + extra
    groups = multi
    other_idx = None
    if singles:
        if ungrouped_first:
            groups = [singles] + multi
            other_idx = 0
        else:
            groups = multi + [singles]
            other_idx = len(groups) - 1
    open_idx = None
    cards_rebuild()
    time_button_update()

def time_button_update():
    culler_time_button.configure(text="Dates: file" if time_mode == 1 else "Dates: EXIF")

def groups_log():
    total = sum(len(g) for g in groups)
    n_groups = len(groups) - (1 if other_idx is not None else 0)
    ungrouped = len(groups[other_idx]) if other_idx is not None else 0
    biggest = max((len(g) for i, g in enumerate(groups) if i != other_idx), default=0)
    logging.info("Grouped %d photos (%s, %s) into %d groups plus %d ungrouped, gap %.0f s, similarity limit %d, biggest group %d, %d exact copies hidden, %d without EXIF hidden.", total, camera_choice, "file dates" if time_mode else "EXIF dates", n_groups, ungrouped, group_gaps[group_level], group_limits[group_level], biggest, len(copy_hidden), hidden_no_exif)
    q.put(("status", f"{n_groups} groups"))
    q.put(("status_reset", None))
    if copy_hidden:
        n = len(copy_hidden)
        q.put(("summary_add", f"○ {n} exact cop{'y' if n == 1 else 'ies'} hidden."))
        q.put(("summary_hide_later", None))

def groups_show():
    grid_clear()
    grid_update_region(grid_geometry())
    pic_canvas.yview_moveto(0)
    empty_update()
    schedule_refresh()
    bottom_bar_update()

def camera_changed(choice):
    global camera_choice
    if scan_active or copies_active:
        return
    camera_choice = choice
    groups_build()
    groups_log()
    groups_show()

def pics_mode_set(value):
    global pics_mode
    new = "all" if value == "All photos" else "groups"
    if new == pics_mode:
        return
    if scan_active or copies_active:
        culler_mode_switch.set("All photos" if pics_mode == "all" else "Groups")
        return
    if open_idx is not None:
        group_close()
    pics_mode = new
    marq_sel.clear()
    hover_clear()
    inspect_close_all()
    compare_close()
    peek_close()
    sel_hide()
    cards_rebuild()
    header_show()
    groups_show()

def sort_cycle():
    global all_sort
    if scan_active or copies_active:
        return
    names = ("Name", "Date", "Camera")
    all_sort = names[(names.index(all_sort) + 1) % 3]
    culler_sort_button.configure(text=f"Sort: {all_sort}")
    cards_rebuild()
    groups_show()
    
def groups_cycle():
    global group_level
    group_level = (group_level + 1) % 3
    culler_groups_button.configure(text=f"Groups: {group_names[group_level]}")
    if scan_active or copies_active or not scan_order:
        return
    groups_build()
    groups_log()
    groups_show()

size_names = ("High", "Medium", "Low")

def pictures_size():
    global size
    if scan_active or copies_active:
        return
    size = (size + 1) % 3
    culler_size_changer.configure(text=f"Density: {size_names[size]}")
    hover_clear()
    grid_clear()
    grid_update_region(grid_geometry())
    pic_canvas.yview_moveto(0)
    schedule_refresh()
    sel_scroll_into_view()

def time_toggle():
    global time_mode
    if scan_active or copies_active:
        return
    time_mode = 1 - time_mode
    groups_build()
    groups_log()
    groups_show()

def camera_menu_show():
    if len(camera_names) > 1:
        culler_camera_menu.grid(row=0, column=0, padx=(0, 8))
    else:
        culler_camera_menu.grid_forget()

def header_show():
    if open_idx is None:
        culler_group_tools.grid_forget()
        culler_tools.grid(row=1, column=0, columnspan=3, sticky="w", padx=(16, 0), pady=10)
        if pics_mode == "all":
            culler_groups_button.grid_forget()
            culler_time_button.grid_forget()
            culler_sort_button.grid(row=0, column=1, padx=(0, 6))
        else:
            culler_sort_button.grid_forget()
            culler_groups_button.grid(row=0, column=1, padx=(0, 6))
            culler_time_button.grid(row=0, column=2, padx=(0, 6))
        camera_menu_show()
    else:
        culler_tools.grid_forget()
        culler_group_tools.grid(row=1, column=0, columnspan=3, sticky="w", padx=(16, 0), pady=10)
        group_buttons_update()

def empty_update():
    if cards or scan_active or copies_active or "target_folder" not in globals():
        culler_empty.grid_forget()
        return
    if not scan_order:
        text = "No pictures in this folder."
    elif time_mode == 0 and hidden_no_exif:
        text = f"No photos with an EXIF date here.\nPress the time button to use file dates and show all {hidden_no_exif} photos."
    else:
        text = "Nothing to show."
    culler_empty.configure(text=text)
    culler_empty.grid(row=1, pady=60)

def group_title(idx):
    count = len(groups[idx])
    plural = "" if count == 1 else "s"
    if idx == other_idx:
        return f"Ungrouped · {count} photo{plural}"
    number = idx + 1 - (1 if other_idx is not None and other_idx < idx else 0)
    total = len(groups) - (1 if other_idx is not None else 0)
    return f"Group {number} of {total} · {count} photo{plural}"


def stack_rects(idx, geo):
    row, col = divmod(idx, geo["per_row"])
    x = geo["left"] + col * (geo["w"] + geo["gap_x"])
    y = geo["top"] + row * geo["pitch"]
    n = min(len(cards[idx]), stack_limit)
    peek = stack_peek * geo["s"]
    inset = stack_inset * geo["s"]
    card_h = geo["h"] - (n - 1) * peek
    return [(x + k * inset, y + (n - 1 - k) * peek, geo["w"] - 2 * k * inset, card_h) for k in range(n)]

def pill_draw(items, left, top, text, fill, s, font):
    box_w = (14 + 8 * len(text)) * s
    box_h = 20 * s
    items.append(pic_canvas.create_rectangle(left, top, left + box_w, top + box_h, fill=fill, outline=""))
    items.append(pic_canvas.create_text(left + box_w / 2, top + box_h / 2, text=text, fill="white", font=font))

def badge_draw(idx, rect, geo):
    card = cards[idx]
    left, top, w, h = rect
    s = geo["s"]
    items = []
    grouped = at_groups()
    font = ("Bahnschrift Light Condensed", -round(15 * s), "bold")
    if grouped and idx == other_idx:
        bar_h = 24 * s
        items.append(pic_canvas.create_rectangle(left, top + h - bar_h, left + w, top + h, fill="#173348", outline=""))
        items.append(pic_canvas.create_text(left + w / 2, top + h - bar_h / 2, text=f"UNGROUPED · {len(card)}", fill="white", font=font))
    elif grouped and len(card) >= 2:
        text = str(len(card))
        pill_draw(items, left + w - 6 * s - (14 + 8 * len(text)) * s, top + 6 * s, text, "#1f6aa5", s, font)
    if grouped and idx != other_idx and group_is_done(idx):
        bar_h = 24 * s
        items.append(pic_canvas.create_rectangle(left, top + h - bar_h, left + w, top + h, fill="#2e8b57", outline=""))
        items.append(pic_canvas.create_text(left + w / 2, top + h - bar_h / 2, text="FINISHED ✓", fill="white", font=font))
    if grouped:
        kept = sum(1 for f in card if str(f) in keep_set)
        if kept:
            pill_draw(items, left + 6 * s, top + 6 * s, f"✓ {kept}", "#2e8b57", s, font)
    else:
        box = tick_box * s
        x1 = left + 6 * s
        y1 = top + 6 * s
        is_kept = str(card[0]) in keep_set
        items.append(pic_canvas.create_rectangle(x1, y1, x1 + box, y1 + box, fill="#2e8b57" if is_kept else "#101117", outline="white", width=2))
        if is_kept:
            items.append(pic_canvas.create_text(x1 + box / 2, y1 + box / 2, text="✓", fill="white", font=font))
        tag = suggest_tags.get(card[0])
        if tag:
            if tag == "best":
                items.append(pic_canvas.create_rectangle(left, top, left + w, top + h, outline=BEST_COLOR, width=4))
            text, color = ("★", BEST_COLOR) if tag == "best" else ("SOFT", SOFT_COLOR)
            pill_draw(items, left + w - 6 * s - (14 + 8 * len(text)) * s, top + 6 * s, text, color, s, font)
    if items:
        pic_badges[idx] = items

def cell_remove(idx):
    for layer in range(stack_limit):
        ck = (idx, layer)
        rect_id = pic_cells.pop(ck, None)
        if rect_id is not None:
            pic_canvas.delete(rect_id)
        image_id = pic_images.pop(ck, None)
        if image_id is not None:
            pic_canvas.delete(image_id)
        cell_info.pop(ck, None)
    for item_id in pic_badges.pop(idx, ()):
        pic_canvas.delete(item_id)

def cell_make(idx, geo):
    rects = stack_rects(idx, geo)
    for layer in range(len(rects) - 1, -1, -1):
        left, top, w, h = rects[layer]
        ck = (idx, layer)
        pic_cells[ck] = pic_canvas.create_rectangle(left, top, left + w, top + h, fill=cell_color, outline=card_edge, width=2)
        cell_info[ck] = (round(w), round(h), 1 if layer else 0)
    badge_draw(idx, rects[0], geo)
    for layer in range(len(rects)):
        thumb_request((idx, layer))

def badge_refresh(idx):
    if (idx, 0) not in pic_cells:
        return
    for item_id in pic_badges.pop(idx, ()):
        pic_canvas.delete(item_id)
    geo = grid_geometry()
    badge_draw(idx, stack_rects(idx, geo)[0], geo)
    pic_canvas.tag_raise("sel")

def card_redraw(idx):
    cell_remove(idx)
    cell_make(idx, grid_geometry())
    pic_canvas.tag_raise("sel")

def grid_clear():
    global hover_idx
    hover_idx = None
    pic_canvas.delete("all")
    pic_cells.clear()
    pic_images.clear()
    pic_badges.clear()
    cell_info.clear()

def grid_update_region(geo):
    global pic_total_h
    n_rows = (len(pending_pics) + geo["per_row"] - 1) // geo["per_row"]
    pic_total_h = geo["slot0"] + n_rows * geo["pitch"] if n_rows else 0
    pic_canvas.configure(scrollregion=(0, 0, view_w * geo["s"], max(pic_total_h, 1)))
    return pic_total_h

def folder_stamp():
    try:
        return target_folder.stat().st_mtime_ns
    except OSError:
        return None

sessions_file = path / "sessions.json"
session_folder = None

def sessions_load():
    try:
        with open(sessions_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}

sessions = sessions_load()

def sessions_save():
    tmp = sessions_file.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(sessions, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, sessions_file)
    except OSError:
        logging.exception("Could not save the session list.")

def folder_cache_info():
    folder = str(target_folder)
    kept = sum(1 for k in keep_set if os.path.dirname(k) == folder)
    finished = sum(1 for k in done_set if os.path.dirname(k) == folder)
    scanned = sum(1 for k in photo_cache if os.path.dirname(k) == folder)
    return kept, finished, scanned

def folder_cache_clear():
    folder = str(target_folder)
    for store, save in ((keep_set, keep_save), (done_set, done_save)):
        stale = {k for k in store if os.path.dirname(k) == folder}
        if stale:
            store.difference_update(stale)
            save()
    old = [k for k in photo_cache if os.path.dirname(k) == folder]
    for k in old:
        del photo_cache[k]
    if old:
        cache_save(dict(photo_cache))
    sessions.pop(folder, None)
    sessions_save()
    logging.info("Cleared saved data for %s (%d scanned photos).", folder, len(old))

def folder_cache_ask():
    global session_folder
    if session_folder == target_folder:
        return True
    folder = str(target_folder)
    kept, finished, scanned = folder_cache_info()
    if kept or finished or scanned:
        opened = sessions.get(folder)
        when = f"\nLast opened: {opened}." if opened else ""
        name = target_folder.name or str(target_folder)
        choice = messagebox.askyesnocancel("Specorde", f"Saved progress found for '{name}': {scanned} photos read, {kept} kept, {finished} in finished groups.{when}\n\nYes = continue where you left off\nNo = start over (clears the marks and the saved scan for this folder)\nCancel = don't open this folder now")
        if choice is None:
            return False
        if choice is False:
            folder_cache_clear()
    session_folder = target_folder
    sessions[folder] = datetime.now().strftime("%Y-%m-%d %H:%M")
    sessions_save()
    return True

def grid_load_folder():
    global pending_pics
    global pics_folder
    global pics_stamp
    global scan_token
    global scan_total
    global scan_done
    global scan_active
    global scan_started
    global scan_order
    global photo_info
    global groups
    global cards
    global open_idx
    global other_idx
    global copy_hidden
    global copies_active
    global camera_names
    global camera_choice
    global hidden_no_exif
    pics_folder = target_folder
    pics_stamp = folder_stamp()
    marq_sel.clear()
    if not folder_cache_ask():
        scan_token += 1
        scan_active = False
        copies_active = False
        pics_folder = None
        pending_pics = []
        groups = []
        cards = []
        open_idx = None
        inspect_close_all()
        header_show()
        grid_clear()
        culler_loading.grid_forget()
        overview_frame.grid_forget()
        cutesy_bar.grid_forget()
        culler_empty.configure(text="Cancelled. Press Culler again to open this folder.")
        culler_empty.grid(row=1, pady=60)
        return
    try:
        pics = [p for p in target_folder.iterdir() if p.is_file() and p.suffix.lower() in pic_suffixes and not is_protected_item(p)]
    except OSError:
        logging.exception("Could not read pictures from %s", target_folder)
        pics = []
    pics.sort(key=lambda p: p.name.lower())
    scan_token += 1
    scan_order = pics
    photo_info = {}
    scan_stats.update(cached=0, failed=0, new=0)
    scan_total = len(pics)
    scan_done = 0
    scan_started = time.perf_counter()
    scan_active = True
    copies_active = False
    copy_hidden = set()
    pending_pics = []
    groups = []
    cards = []
    open_idx = None
    other_idx = None
    camera_names = []
    camera_choice = all_cameras
    hidden_no_exif = 0
    inspect_close_all()
    header_show()
    culler_camera_menu.grid_forget()
    culler_empty.grid_forget()
    grid_clear()
    grid_update_region(grid_geometry())
    overview_frame.grid_forget()
    cutesy_bar.grid_forget()
    culler_loading.configure(text=f"Reading photos 0/{scan_total}")
    culler_loading.grid(row=1, pady=20)
    q.put(("status", "Reading photos..."))
    for file in pics:
        scan_requests.put((scan_token, file))
    if not pics:
        scan_finish()

def grid_refresh():
    global grid_job
    global grid_scale
    grid_job = None
    if not cards:
        return
    geo = grid_geometry()
    if geo["s"] != grid_scale:
        grid_scale = geo["s"]
        grid_clear()
        pic_canvas.configure(width=round(view_w * grid_scale), height=round(view_h_base * grid_scale))
        grid_update_region(geo)
    per_row = geo["per_row"]
    pitch = geo["pitch"]
    n = len(cards)
    n_rows = (n + per_row - 1) // per_row
    top = pic_canvas.canvasy(0)
    view_h = grid_view_h(geo)
    first_row = max(int((top - geo["slot0"]) // pitch) - grid_buffer_rows, 0)
    last_row = min(int((top + view_h - geo["slot0"]) // pitch) + grid_buffer_rows, n_rows - 1)
    first_idx = first_row * per_row
    last_idx = min((last_row + 1) * per_row, n)

    for idx in {ck[0] for ck in pic_cells if ck[0] < first_idx or ck[0] >= last_idx}:
        cell_remove(idx)

    shown = {ck[0] for ck in pic_cells}
    mid_idx = int((top + view_h / 2 - geo["slot0"]) // pitch) * per_row
    new_idxs = [i for i in range(first_idx, last_idx) if i not in shown]
    new_idxs.sort(key=lambda i: abs(i - mid_idx), reverse=True)

    for idx in new_idxs:
        cell_make(idx, geo)
    sel_draw()
    banner_draw()
    marq_draw()

def schedule_refresh():
    global grid_job
    if grid_job is None:
        grid_job = pic_canvas.after_idle(grid_refresh)

def on_yscroll(first, last):
    pic_scroll.set(first, last)
    schedule_refresh()

def pic_wheel(event):
    view_h = pic_canvas.winfo_height()
    if pic_total_h <= view_h:
        return "break"
    hover_clear()
    step = max(-wheel_max_step, min(wheel_max_step, event.delta * wheel_speed))
    new_top = max(0, min(pic_canvas.canvasy(0) - step, pic_total_h - view_h))
    pic_canvas.yview_moveto(new_top / pic_total_h)
    return "break"

def card_at(event):
    geo = grid_geometry()
    x = pic_canvas.canvasx(event.x) - geo["left"]
    y = pic_canvas.canvasy(event.y) - geo["top"]
    if x < 0 or y < 0:
        return None
    col = int(x // (geo["w"] + geo["gap_x"]))
    row = int(y // geo["pitch"])
    if col >= geo["per_row"]:
        return None
    if x - col * (geo["w"] + geo["gap_x"]) > geo["w"] or y - row * geo["pitch"] > geo["h"]:
        return None
    idx = row * geo["per_row"] + col
    return idx if idx < len(cards) else None

def hover_clear():
    global hover_idx
    hover_idx = None
    pic_canvas.delete("hover")
    pic_canvas.configure(cursor="")

def pic_hover(event):
    global hover_idx
    idx = card_at(event)
    if idx == hover_idx:
        return
    if idx is not None and sel_visible:
        sel_hide()
    hover_idx = idx
    pic_canvas.delete("hover")
    if idx is None:
        pic_canvas.configure(cursor="")
        return
    pic_canvas.configure(cursor="hand2")
    rects = stack_rects(idx, grid_geometry())
    left = rects[0][0]
    top = rects[-1][1]
    right = left + rects[0][2]
    bottom = rects[0][1] + rects[0][3]
    pad = 3 * ui_scale()
    pic_canvas.create_rectangle(left - pad, top - pad, right + pad, bottom + pad, outline=hover_color, width=2, tags="hover")

hold_ms = 250
press_x = 0
press_y = 0
last_click_time = 0.0
press_on_tick = False
marq_sel = set()
marq_base = set()
marq_on = False
marq_add = False
marq_x0 = 0.0
marq_y0 = 0.0
marq_last = -1
press_mods = 0
sel_anchor = None
auto_job = None
auto_speed = 0.0
marq_ptr = (0, 0)
pics_mode = "all"
all_sort = "Name"
move_limit = 8
tick_box = 26
tick_zone = 38
inspect_buttons = {}
last_click_idx = None
DIFF_THRESHOLD = 22
DIFF_COLORS = ["#00e5ff", "#ff8a1f", "#9dff3a", "#ff3aa8"]
press_job = None
press_idx = None
peek_window = None
compare_window = None
inspect_windows = []
inspect_by_file = {}
rejected_name = "rejected_specorde"
UI_FONT = "Bahnschrift Light Condensed"
sel_idx = None
sel_visible = False

def center_on_main(win, offset=0):
    win.update_idletasks()
    w = win.winfo_reqwidth()
    h = win.winfo_reqheight()
    x = canvas.winfo_x() + (canvas.winfo_width() - w) // 2 + offset
    y = canvas.winfo_y() + (canvas.winfo_height() - h) // 2 + offset
    tk.Wm.geometry(win, f"+{max(x, 0)}+{max(y, 0)}")

def set_inspect_icon(win):
    try:
        if win.winfo_exists():
            win.iconbitmap(str(resource_path("specorde_logo.ico")))
    except Exception:
        logging.exception("Window icon failed.")

def card_index_of(file):
    for i, card in enumerate(cards):
        if card[0] == file:
            return i
    return None

def group_kept_files():
    if open_idx is None:
        return [], []
    files = groups[open_idx]
    kept = [f for f in files if str(f) in keep_set]
    rest = [f for f in files if str(f) not in keep_set]
    return kept, rest
def clear_kept():
    kept, _ = group_kept_files()
    if not kept:
        return
    compare_close()
    for f in kept:
        keep_set.discard(str(f))
    keep_save()
    for f in kept:
        keep_refresh(f)

btn_state = {}

def btn_set(button, **new):
    old = btn_state.setdefault(button, {})
    changed = {k: v for k, v in new.items() if old.get(k) != v}
    if changed:
        old.update(changed)
        button.configure(**changed)

def bottom_bar_update():
    n = len(marq_sel)
    kept = kept_count()
    if n:
        text = f"{n} selected · {kept} kept"
    elif at_singles():
        text = f"{kept} kept · drag to select photos"
    else:
        text = f"{kept} kept"
    if bar_info.cget("text") != text:
        bar_info.configure(text=text)
    if n and not bar_keep_button.winfo_ismapped():
        bar_keep_button.grid(row=0, column=1, padx=(0, 6), pady=5)
        bar_unkeep_button.grid(row=0, column=2, padx=(0, 6), pady=5)
        bar_clear_button.grid(row=0, column=3, padx=(0, 6), pady=5)
    elif not n and bar_keep_button.winfo_ismapped():
        bar_keep_button.grid_forget()
        bar_unkeep_button.grid_forget()
        bar_clear_button.grid_forget()
    can_edit = at_singles() and bool(cards)
    btn_set(bar_edit_button, state="normal" if can_edit else "disabled", fg_color="#1f6aa5" if can_edit else IDLE_COLOR)
    btn_set(bar_bulk_button, text=f"Bulk edit ({n or kept})")
    can_wrap = open_idx is None
    btn_set(bar_wrap_button, state="normal" if can_wrap else "disabled", fg_color="#1f6aa5" if can_wrap else IDLE_COLOR)

def group_buttons_update():
    if open_idx is None:
        return
    kept, rest = group_kept_files()
    can_compare = 2 <= len(kept) <= 4
    btn_set(culler_compare_button, text="Compare" if len(kept) < 2 else f"Compare {len(kept)}", state="normal" if can_compare else "disabled", fg_color="#1f6aa5" if can_compare else "#173348")
    btn_set(culler_clear_button, state="normal" if kept else "disabled", fg_color="#1f6aa5" if kept else "#173348")
    can_delete = bool(kept) and bool(rest) and open_idx != other_idx
    btn_set(culler_delete_button, state="normal" if can_delete else "disabled", fg_color="#8b2e2e" if can_delete else "#173348")
    suggest_button_update()

def inspect_close_all():
    for win in list(inspect_windows):
        inspect_close(win)

def keep_text(file):
    return "Kept ✓" if str(file) in keep_set else "Keep"

def peek_close(event=None):
    global peek_window
    if peek_window is not None:
        try:
            peek_window.destroy()
        except Exception:
            pass
        peek_window = None

inspect_cache = OrderedDict()
inspect_cache_max = 30
inspect_preload_max = 24
inspect_lock = threading.Lock()

def inspect_box(frac_w=0.42, frac_h=0.5):
    return int(canvas.winfo_screenwidth() * frac_w), int(canvas.winfo_screenheight() * frac_h)

def inspect_load(file, box=None):
    if box is None:
        box = inspect_box()
    box_w, box_h = box
    key = (str(file), box_w, box_h)
    with inspect_lock:
        cached = inspect_cache.get(key)
        if cached is not None:
            inspect_cache.move_to_end(key)
            return cached
    try:
        img = load_image(file, (box_w * 2, box_h * 2), need=max(box_w, box_h))
        img.thumbnail((box_w, box_h))
    except Exception:
        logging.exception("Could not open %s for inspecting.", file.name)
        return None
    with inspect_lock:
        inspect_cache[key] = img
        while len(inspect_cache) > inspect_cache_max:
            inspect_cache.popitem(last=False)
    return img

def inspect_preload(idx):
    box = inspect_box()
    files = list(groups[idx])[:inspect_preload_max]

    def work():
        for file in files:
            if open_idx != idx:
                return
            inspect_load(file, box)

    threading.Thread(target=work, daemon=True).start()

class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

def monitor_area(x, y):
    try:
        point = wintypes.POINT(int(x), int(y))
        monitor = ctypes.windll.user32.MonitorFromPoint(point, 2)
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if ctypes.windll.user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            r = info.rcWork
            return r.left, r.top, r.right, r.bottom
    except Exception:
        logging.exception("Could not read the monitor area.")
    return 0, 0, canvas.winfo_screenwidth(), canvas.winfo_screenheight()

def reveal(win):
    try:
        if win.winfo_exists():
            win.deiconify()
            win.lift()
            win.focus_force()
    except Exception:
        pass

def place_at_mouse(win, x, y):
    win.update_idletasks()
    w = win.winfo_reqwidth()
    h = win.winfo_reqheight()
    left, top, right, bottom = monitor_area(x, y)
    px = min(max(x - w // 2, left), max(right - w, left))
    py = min(max(y - h // 2, top), max(bottom - h, top))
    logging.debug("place_at_mouse: mouse=(%s,%s) size=%sx%s monitor=%s result=(%s,%s)", x, y, w, h, (left, top, right, bottom), px, py)

    def apply():
        try:
            if win.winfo_exists():
                tk.Wm.geometry(win, f"+{px}+{py}")
        except Exception:
            logging.exception("Could not place the window.")

    apply()
    win.after(30, apply)
    win.after(350, apply)

def peek_start():
    global press_job, peek_window
    press_job = None
    if press_idx is None or press_idx >= len(cards):
        return
    img = inspect_load(cards[press_idx][0])
    if img is None:
        return
    hover_clear()
    photo = ImageTk.PhotoImage(img)
    win = tk.Toplevel(canvas)
    win.overrideredirect(True)
    win.configure(bg=card_edge)
    win.withdraw()
    label = tk.Label(win, image=photo, bd=0, bg="#101117")
    label.image = photo
    label.pack(padx=3, pady=3)
    place_at_mouse(win, press_x, press_y)
    win.deiconify()
    win.attributes("-topmost", True)
    win.bind("<ButtonRelease-1>", peek_close)
    peek_window = win

def click_cancel():
    global last_click_idx
    last_click_idx = None

def tick_hit(event, idx):
    geo = grid_geometry()
    left, top, w, h = stack_rects(idx, geo)[0]
    x = pic_canvas.canvasx(event.x)
    y = pic_canvas.canvasy(event.y)
    zone = tick_zone * geo["s"]
    return left <= x <= left + zone and top <= y <= top + zone

def at_groups():
    return open_idx is None and pics_mode == "groups"

def at_singles():
    return not at_groups()

def kept_count():
    if "target_folder" not in globals():
        return 0
    folder = str(target_folder)
    return sum(1 for k in keep_set if os.path.dirname(k) == folder)

def marq_hits(x1, y1, x2, y2):
    geo = grid_geometry()
    r0 = max(0, int((y1 - geo["top"]) // geo["pitch"]))
    r1 = int((y2 - geo["top"]) // geo["pitch"])
    out = []
    for row in range(r0, r1 + 1):
        for col in range(geo["per_row"]):
            idx = row * geo["per_row"] + col
            if idx >= len(cards):
                break
            l, t, w, h = stack_rects(idx, geo)[0]
            if l < x2 and l + w > x1 and t < y2 and t + h > y1:
                out.append(idx)
    return out

def marq_draw():
    pic_canvas.delete("msel")
    if not marq_sel or not cards or at_groups():
        return
    geo = grid_geometry()
    top = pic_canvas.canvasy(0)
    view_h = grid_view_h(geo)
    r0 = max(0, int((top - geo["slot0"]) // geo["pitch"]))
    r1 = int((top + view_h - geo["slot0"]) // geo["pitch"])
    pad = 3 * geo["s"]
    for idx in range(r0 * geo["per_row"], min((r1 + 1) * geo["per_row"], len(cards))):
        if cards[idx][0] in marq_sel:
            l, t, w, h = stack_rects(idx, geo)[0]
            pic_canvas.create_rectangle(l - pad, t - pad, l + w + pad, t + h + pad, outline="#4da3ff", width=3, tags="msel")

def rubber_draw(x, y):
    pic_canvas.delete("rubber")
    pic_canvas.create_rectangle(marq_x0, marq_y0, x, y, outline="#4da3ff", fill="#4da3ff", stipple="gray25", tags="rubber")

def marq_clear():
    marq_sel.clear()
    pic_canvas.delete("msel")
    pic_canvas.delete("rubber")
    bottom_bar_update()

def marq_all():
    marq_sel.clear()
    marq_sel.update(c[0] for c in cards)
    marq_draw()
    bottom_bar_update()
    return "break"

def marq_keep(value):
    changed = False
    for card in cards:
        key = str(card[0])
        if card[0] in marq_sel and (key in keep_set) != value:
            if value:
                keep_set.add(key)
            else:
                keep_set.discard(key)
            changed = True
    if changed:
        keep_save_later()
        for i in range(len(cards)):
            if (i, 0) in pic_cells:
                badge_refresh(i)
        group_buttons_update()
    bottom_bar_update()

def click_select(idx, shift, ctrl):
    global sel_anchor
    if shift and sel_anchor is not None and sel_anchor < len(cards):
        a, b = sorted((sel_anchor, idx))
        if not ctrl:
            marq_sel.clear()
        marq_sel.update(c[0] for c in cards[a:b + 1])
    else:
        file = cards[idx][0]
        if file in marq_sel:
            marq_sel.discard(file)
        else:
            marq_sel.add(file)
        sel_anchor = idx
    marq_draw()
    bottom_bar_update()

def marq_update():
    x = pic_canvas.canvasx(marq_ptr[0])
    y = pic_canvas.canvasy(marq_ptr[1])
    left, right = sorted((marq_x0, x))
    top, bottom = sorted((marq_y0, y))
    hit = {cards[i][0] for i in marq_hits(left, top, right, bottom)}
    marq_sel.clear()
    marq_sel.update(marq_base | hit)
    rubber_draw(x, y)
    marq_draw()

def auto_scroll_tick():
    global auto_job
    auto_job = None
    view_h = pic_canvas.winfo_height()
    if not marq_on or not auto_speed or pic_total_h <= view_h:
        return
    new_top = max(0, min(pic_canvas.canvasy(0) + auto_speed, pic_total_h - view_h))
    pic_canvas.yview_moveto(new_top / pic_total_h)
    marq_update()
    bottom_bar_update()
    auto_job = pic_canvas.after(16, auto_scroll_tick)

def pic_press(event):
    global press_job, press_idx, press_x, press_y, press_on_tick, marq_on, marq_x0, marq_y0, marq_add, press_mods
    canvas.focus_set()
    sel_hide()
    peek_close()
    marq_on = False
    press_mods = event.state
    marq_x0 = pic_canvas.canvasx(event.x)
    marq_y0 = pic_canvas.canvasy(event.y)
    marq_add = bool(event.state & 0x5)
    press_idx = card_at(event)
    press_x = event.x_root
    press_y = event.y_root
    press_on_tick = at_singles() and press_idx is not None and tick_hit(event, press_idx)
    if press_idx is not None and not press_on_tick:
        press_job = pic_canvas.after(hold_ms, peek_start)

def pic_drag(event):
    global press_job, press_idx, marq_on, marq_base, marq_last, marq_ptr, auto_speed, auto_job
    if peek_window is not None:
        return
    if not marq_on:
        if math.hypot(event.x_root - press_x, event.y_root - press_y) < move_limit:
            return
        if press_job is not None:
            pic_canvas.after_cancel(press_job)
            press_job = None
        if at_groups():
            press_idx = None
            return
        marq_on = True
        marq_last = -1
        marq_base = set(marq_sel) if marq_add else set()
        hover_clear()
        click_cancel()
    marq_ptr = (event.x, event.y)
    view_h = pic_canvas.winfo_height()
    edge = 40
    if event.y < edge:
        auto_speed = -min(60.0, (edge - event.y) * 0.5 + 4)
    elif event.y > view_h - edge:
        auto_speed = min(60.0, (event.y - (view_h - edge)) * 0.5 + 4)
    else:
        auto_speed = 0.0
    if auto_speed and auto_job is None:
        auto_job = pic_canvas.after(16, auto_scroll_tick)
    marq_update()
    if len(marq_sel) != marq_last:
        marq_last = len(marq_sel)
        bottom_bar_update()

def pic_release(event):
    global press_job, press_idx, last_click_idx, last_click_time, press_on_tick, marq_on
    if peek_window is not None:
        peek_close()
        press_idx = None
        press_on_tick = False
        return
    if marq_on:
        marq_on = False
        pic_canvas.delete("rubber")
        press_idx = None
        press_on_tick = False
        bottom_bar_update()
        return
    if press_job is not None:
        pic_canvas.after_cancel(press_job)
        press_job = None
    idx = card_at(event)
    started = press_idx
    on_tick = press_on_tick
    press_idx = None
    press_on_tick = False
    if idx is None and started is None and marq_sel:
        marq_clear()
        return
    if idx is None or idx != started:
        return
    if at_groups():
        group_open(idx)
        return
    if press_mods & 0x5:
        click_select(idx, bool(press_mods & 0x1), bool(press_mods & 0x4))
        return
    if on_tick and tick_hit(event, idx):
        last_click_idx = None
        keep_flip(idx)
        return
    now = time.perf_counter()
    if last_click_idx == idx and now - last_click_time <= dbl_ms / 1000:
        last_click_idx = None
        keep_flip(idx)
        inspect_show(idx, event.x_root, event.y_root)
        return
    keep_flip(idx)
    last_click_idx = idx
    last_click_time = now

def keep_refresh(file):
    i = card_index_of(file)
    if i is not None:
        badge_refresh(i)
    button = inspect_buttons.get(file)
    if button is not None:
        try:
            button.configure(text=keep_text(file))
        except Exception:
            inspect_buttons.pop(file, None)
    group_buttons_update()
    bottom_bar_update()

def keep_flip(idx):
    file = cards[idx][0]
    lock_toggle(file)
    keep_refresh(file)

def compare_close(event=None):
    global compare_window
    if compare_window is not None:
        try:
            compare_window.destroy()
        except Exception:
            pass
        compare_window = None
        main_focus_later()

def shift_search(a, b, cx, cy, radius):
    w, h = a.size
    margin = max(abs(cx), abs(cy)) + radius
    if margin * 2 >= min(w, h) - 8:
        return cx, cy
    ca = a.crop((margin, margin, w - margin, h - margin))
    best = None
    for dy in range(cy - radius, cy + radius + 1):
        for dx in range(cx - radius, cx + radius + 1):
            cb = b.crop((margin + dx, margin + dy, w - margin + dx, h - margin + dy))
            score = ImageStat.Stat(ImageChops.difference(ca, cb)).mean[0]
            if best is None or score < best[0]:
                best = (score, dx, dy)
    return best[1], best[2]

def estimate_shift(a, b):
    w, h = a.size
    widths = [x for x in (128, 384) if x < w] + [w]
    dx = dy = 0
    prev = None
    for tw in widths:
        th = max(round(h * tw / w), 1)
        sa = a if tw == w else a.resize((tw, th), Image.BILINEAR)
        sb = b if tw == w else b.resize((tw, th), Image.BILINEAR)
        if prev is None:
            radius = 12
        else:
            f = tw / prev
            dx, dy = round(dx * f), round(dy * f)
            radius = int(f) + 1
        dx, dy = shift_search(sa, sb, dx, dy, radius)
        prev = tw
    return dx, dy

def trim(text, limit=28):
    return text if len(text) <= limit else text[:limit - 3] + "..."

def fit_down(img, box):
    copy = img.copy()
    copy.thumbnail(box, Image.BILINEAR)
    return copy

def diff_align(images):
    w, h = images[0].size
    grays = [im.convert("L") for im in images]
    shifts = [(0, 0)] + [estimate_shift(grays[0], g) for g in grays[1:]]
    m = max(max(abs(dx), abs(dy)) for dx, dy in shifts) + 3
    if m * 2 >= min(w, h) - 20:
        m = 0
    box = (m, m, w - m, h - m)
    colors = []
    for im, (dx, dy) in zip(images, shifts):
        moved = im if (dx, dy) == (0, 0) else im.transform((w, h), Image.AFFINE, (1, 0, dx, 0, 1, dy), resample=Image.BILINEAR)
        colors.append(moved.crop(box))
    grays = [c.convert("L") for c in colors]
    mean0 = ImageStat.Stat(grays[0]).mean[0]
    for k in range(1, len(grays)):
        off = mean0 - ImageStat.Stat(grays[k]).mean[0]
        grays[k] = grays[k].point(lambda v, o=off: max(0, min(255, int(v + o))))
    return {"color": colors, "gray": grays, "size": colors[0].size}

def diff_highlight(data, names):
    gray = data["gray"]
    size = data["size"]
    blur = [g.filter(ImageFilter.GaussianBlur(2)) for g in gray]
    out = gray[0].point(lambda v: int(v * 0.45 + 18)).convert("RGB")
    black = Image.new("RGB", size, (0, 0, 0))
    changed = Image.new("L", size, 0)
    legend = []
    if len(gray) == 2:
        specs = [
            (ImageChops.subtract(blur[0], blur[1]), gray[0], DIFF_COLORS[0], f"Brighter in {trim(names[0])}"),
            (ImageChops.subtract(blur[1], blur[0]), gray[1], DIFF_COLORS[1], f"Brighter in {trim(names[1])}"),
        ]
    else:
        legend.append(("#8a8f9c", f"Base: {trim(names[0])}"))
        specs = [(ImageChops.difference(blur[0], blur[k]), gray[k], DIFF_COLORS[k - 1], f"{trim(names[k])} differs") for k in range(1, len(gray))]
    for delta, src, color, label in specs:
        mask = delta.point(lambda v: 255 if v > DIFF_THRESHOLD else 0)
        mask = mask.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(7))
        changed = ImageChops.lighter(changed, mask)
        soft = mask.filter(ImageFilter.GaussianBlur(2))
        tinted = ImageOps.colorize(src, black="#0b0c10", white=color)
        layer = Image.composite(tinted, black, soft)
        edge = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(5)), mask)
        edge_layer = Image.composite(Image.new("RGB", size, color), black, edge)
        out = ImageChops.screen(out, layer)
        out = ImageChops.screen(out, edge_layer)
        legend.append((color, label))
    pct = changed.histogram()[255] * 100 / (size[0] * size[1])
    return out, legend, pct

COMPARE_MODES = ("Side by side", "Blink", "Slider", "Highlights")
DIFF_MODES = ("Highlights",)
PAD_COLOR = "#101117"
MODE_HELP = {
    "Side by side": "Scroll to zoom · drag to pan · A D pick · R keeps",
    "Slider": "",
    "Highlights": "Glow = where the shots differ",
}
zoom_source_side = 4000
zoom_step = 1.25
zoom_cap = 10.0

def compare_open():
    global compare_window
    kept, _ = group_kept_files()
    n = len(kept)
    if not 2 <= n <= 4:
        return
    compare_close()
    sw = canvas.winfo_screenwidth()
    sh = canvas.winfo_screenheight()
    max_w = int(sw * 0.86)
    max_h = int(sh * 0.56)
    originals = []
    try:
        for f in kept:
            img = load_image(f, (max_w * 2, max_h * 2), need=max(max_w, max_h))
            img.thumbnail((max_w, max_h))
            originals.append(img)
    except Exception:
        logging.exception("Could not open photos for comparing.")
        return
    base = originals[0].size
    shared = [i if i.size == base else ImageOps.pad(i, base, method=Image.BILINEAR, color=PAD_COLOR) for i in originals]
    ratios = [i.size[0] / i.size[1] for i in originals]
    shapes_differ = max(ratios) / min(ratios) > 1.05
    cell_w = max((max_w - 28 * n) // n, 120)
    names = [f.name for f in kept]

    win = ctk.CTkToplevel(canvas)
    win.withdraw()
    win.title("Compare")
    win.configure(fg_color=PAD_COLOR)
    win.resizable(False, False)
    win.transient(canvas)
    win.protocol("WM_DELETE_WINDOW", compare_close)
    compare_window = win

    side_photos = [ImageTk.PhotoImage(fit_down(i, (cell_w, max_h))) for i in originals]
    full_photos = [ImageTk.PhotoImage(i) for i in shared]

    modes = ctk.CTkFrame(win, fg_color="transparent")
    modes.grid(row=0, column=0, pady=(12, 4))
    stage = tk.Frame(win, bg=PAD_COLOR, width=max_w + 32, height=max_h + 96)
    stage.grid(row=1, column=0, padx=16, pady=4)
    view = tk.Frame(stage, bg=PAD_COLOR)
    view.place(relx=0.5, rely=0.5, anchor="center")
    caption = tk.Label(win, text="", bg=PAD_COLOR, fg="#c8ccd8", font=(UI_FONT, 12), wraplength=max_w, justify="center", height=2)
    caption.grid(row=2, column=0, pady=(2, 4))
    legend_box = tk.Frame(win, bg=PAD_COLOR, width=max_w, height=30)
    legend_box.grid(row=3, column=0, pady=(0, 12))
    legend_frame = tk.Frame(legend_box, bg=PAD_COLOR)
    legend_frame.place(relx=0.5, rely=0.5, anchor="center")
    state = {"mode": "Side by side", "blink": 0, "pair": 0, "label": None, "diff": None, "busy": False, "views": {}, "zoom": 1.0, "cx": 0.5, "cy": 0.5, "src": list(originals), "pick": 0, "cells": [], "shown": [], "drag": None, "side_job": None}

    def blink_caption():
        i = state["blink"]
        caption.configure(text=f"{trim(names[i])}  ({i + 1}/{n})")

    def flip(event=None):
        if state["mode"] != "Blink" or state["label"] is None:
            return
        state["blink"] = (state["blink"] + 1) % n
        state["label"].configure(image=full_photos[state["blink"]])
        blink_caption()

    def choose(file):
        for f in kept:
            if f != file and str(f) in keep_set:
                lock_toggle(f)
        if str(file) not in keep_set:
            lock_toggle(file)
        for f in kept:
            keep_refresh(f)
        compare_close()

    def next_pair():
        state["pair"] += 1
        draw()

    def side_zmax():
        ratios_now = [state["src"][i].size[0] / cell[2] for i, cell in enumerate(state["cells"])]
        if not ratios_now:
            return 1.0
        return max(1.5, min(min(ratios_now), zoom_cap))

    def side_clamp():
        half = 0.5 / state["zoom"]
        state["cx"] = max(half, min(1 - half, state["cx"]))
        state["cy"] = max(half, min(1 - half, state["cy"]))

    def side_render(i):
        cell, item, dw, dh = state["cells"][i]
        zoom = state["zoom"]
        if zoom <= 1.0001:
            photo = side_photos[i]
        else:
            src = state["src"][i]
            src_w, src_h = src.size
            half = 0.5 / zoom
            box = (max(0.0, (state["cx"] - half) * src_w), max(0.0, (state["cy"] - half) * src_h), min(float(src_w), (state["cx"] + half) * src_w), min(float(src_h), (state["cy"] + half) * src_h))
            photo = ImageTk.PhotoImage(src.resize((dw, dh), Image.BILINEAR, box=box))
        state["shown"][i] = photo
        cell.itemconfigure(item, image=photo)

    def side_apply():
        state["side_job"] = None
        try:
            if not win.winfo_exists():
                return
            for i in range(len(state["cells"])):
                side_render(i)
        except Exception:
            logging.exception("Could not redraw the zoomed photos.")

    def side_schedule():
        if state["side_job"] is None:
            state["side_job"] = win.after(16, side_apply)

    def side_wheel(event, i):
        cell, item, dw, dh = state["cells"][i]
        old = state["zoom"]
        new = max(1.0, min(side_zmax(), old * zoom_step ** (event.delta / 120)))
        if new == old:
            return "break"
        px = event.x / dw
        py = event.y / dh
        u = state["cx"] - 0.5 / old + px / old
        v = state["cy"] - 0.5 / old + py / old
        state["zoom"] = new
        state["cx"] = u - px / new + 0.5 / new
        state["cy"] = v - py / new + 0.5 / new
        side_clamp()
        side_schedule()
        return "break"

    def side_press(event):
        state["drag"] = (event.x, event.y)

    def side_drag(event, i):
        cell, item, dw, dh = state["cells"][i]
        last = state["drag"]
        state["drag"] = (event.x, event.y)
        if last is None or state["zoom"] <= 1.0:
            return
        state["cx"] -= (event.x - last[0]) / (dw * state["zoom"])
        state["cy"] -= (event.y - last[1]) / (dh * state["zoom"])
        side_clamp()
        side_schedule()

    def side_toggle(event, i):
        cell, item, dw, dh = state["cells"][i]
        if state["zoom"] > 1.0:
            state["zoom"] = 1.0
            state["cx"] = 0.5
            state["cy"] = 0.5
        else:
            state["zoom"] = side_zmax()
            state["cx"] = event.x / dw
            state["cy"] = event.y / dh
            side_clamp()
        side_schedule()

    def side_reset(event=None):
        state["zoom"] = 1.0
        state["cx"] = 0.5
        state["cy"] = 0.5
        side_schedule()

    def full_begin():
        holder = {}

        def work():
            try:
                images = []
                for f in kept:
                    img = load_image(f, (zoom_source_side * 2, zoom_source_side * 2), need=zoom_source_side // 2)
                    img.thumbnail((zoom_source_side, zoom_source_side))
                    images.append(img)
                holder["images"] = images
            except Exception:
                logging.exception("Could not load the full size photos for zooming.")
                holder["images"] = False

        def poll():
            try:
                if not win.winfo_exists():
                    return
                if "images" not in holder:
                    win.after(120, poll)
                    return
                if holder["images"]:
                    state["src"] = holder["images"]
                    side_schedule()
            except Exception:
                logging.exception("Zoom loading check failed.")

        threading.Thread(target=work, daemon=True).start()
        win.after(120, poll)

    def diff_begin():
        if state["busy"]:
            return
        state["busy"] = True
        holder = {}

        def work():
            try:
                holder["data"] = diff_align(shared)
            except Exception:
                logging.exception("Could not line the photos up.")
                holder["data"] = False

        def poll():
            try:
                if not win.winfo_exists():
                    return
                if "data" not in holder:
                    win.after(80, poll)
                    return
                state["busy"] = False
                state["diff"] = holder["data"]
                if state["mode"] in DIFF_MODES:
                    draw()
            except Exception:
                pass

        threading.Thread(target=work, daemon=True).start()
        win.after(80, poll)

    def diff_view(mode):
        views = state["views"]
        if mode not in views:
            try:
                img, legend, pct = diff_highlight(state["diff"], names)
                views[mode] = (ImageTk.PhotoImage(img), legend, pct)
            except Exception:
                logging.exception("Could not build the %s view.", mode)
                views[mode] = None
        return views[mode]

    def slider_draw():
        k = state["pair"] % (n - 1)
        a, b = shared[k], shared[k + 1]
        wd, ht = a.size
        photo = ImageTk.PhotoImage(a)
        cv = tk.Canvas(view, width=wd, height=ht, bg=PAD_COLOR, highlightthickness=0, cursor="sb_h_double_arrow")
        cv.grid(row=0, column=0)
        cv.create_image(0, 0, image=photo, anchor="nw")
        line = cv.create_line(0, 0, 0, ht, fill="#ffffff", width=2)
        cv.photo = photo

        def wipe(x):
            x = max(0, min(wd, int(x)))
            mixed = a.copy()
            if x < wd:
                mixed.paste(b.crop((x, 0, wd, ht)), (x, 0))
            photo.paste(mixed)
            cv.coords(line, x, 0, x, ht)

        cv.bind("<Motion>", lambda e: wipe(e.x))
        cv.bind("<B1-Motion>", lambda e: wipe(e.x))
        wipe(wd // 2)
        if n > 2:
            ctk.CTkButton(view, text="Next pair", width=100, height=24, corner_radius=0, fg_color="#1f2029", hover_color="#2c3043", font=(UI_FONT, 14), command=next_pair).grid(row=1, column=0, pady=(8, 0))
        caption.configure(text=f"{trim(names[k])}   |   {trim(names[k + 1])}")

    def draw():
        state["cells"] = []
        for w in view.winfo_children():
            w.destroy()
        for w in legend_frame.winfo_children():
            w.destroy()
        state["label"] = None
        mode = state["mode"]
        if mode == "Side by side":
            cells = []
            for i, f in enumerate(kept):
                col = tk.Frame(view, bg=PAD_COLOR, highlightbackground="#ffd24a" if i == state["pick"] else PAD_COLOR, highlightthickness=2, bd=0)
                col.grid(row=0, column=i, padx=6, sticky="n")
                dw = side_photos[i].width()
                dh = side_photos[i].height()
                cell = tk.Canvas(col, width=dw, height=dh, bg=PAD_COLOR, highlightthickness=0, bd=0, cursor="fleur")
                cell.grid(padx=4, pady=4)
                item = cell.create_image(0, 0, image=side_photos[i], anchor="nw")
                cell.bind("<MouseWheel>", lambda e, i=i: side_wheel(e, i))
                cell.bind("<ButtonPress-1>", side_press)
                cell.bind("<B1-Motion>", lambda e, i=i: side_drag(e, i))
                cell.bind("<Double-Button-1>", lambda e, i=i: side_toggle(e, i))
                cells.append((cell, item, dw, dh))
                tk.Label(col, text=trim(f.name), bg=PAD_COLOR, fg="#c8ccd8", font=(UI_FONT, 12)).grid()
                ctk.CTkButton(col, text="Keep this one", width=100, height=22, corner_radius=0, fg_color="#1f2029", hover_color="#2c3043", font=(UI_FONT, 13), command=lambda f=f: choose(f)).grid(pady=6)
            state["cells"] = cells
            state["shown"] = [None] * n
            caption.configure(text=MODE_HELP[mode])
            side_schedule()
        elif mode == "Blink":
            lab = tk.Label(view, image=full_photos[state["blink"]], bd=0, bg=PAD_COLOR, cursor="hand2")
            lab.grid()
            lab.bind("<ButtonRelease-1>", flip)
            ctk.CTkButton(view, corner_radius=0, fg_color="#1f2029", hover_color="#2c3043", text="Keep this one", width=120, height=24, font=(UI_FONT, 14), command=lambda: choose(kept[state["blink"]])).grid(pady=(8, 0))
            state["label"] = lab
            blink_caption()
        elif mode == "Slider":
            slider_draw()
        elif state["diff"] is None:
            diff_begin()
            caption.configure(text="Comparing... lining the photos up first")
        elif state["diff"] is False:
            caption.configure(text="Could not build this view (see the log).")
        else:
            result = diff_view(mode)
            if result is None:
                caption.configure(text="Could not build this view (see the log).")
            else:
                photo, legend, pct = result
                tk.Label(view, image=photo, bd=0, bg=PAD_COLOR).grid()
                info = MODE_HELP[mode]
                if pct is not None and pct >= 0.2:
                    info += f" · {pct:.1f}%"
                if shapes_differ:
                    info += " · the photos have different shapes, so treat this with care"
                caption.configure(text=info)
                for k, (color, label) in enumerate(legend):
                    tk.Label(legend_frame, text="   ", bg=color).grid(row=0, column=2 * k, padx=(10, 4))
                    tk.Label(legend_frame, text=label, bg=PAD_COLOR, fg="#c8ccd8", font=(UI_FONT, 12)).grid(row=0, column=2 * k + 1)
        if not state.get("placed"):
            state["placed"] = True
            center_on_main(win)

    def set_mode(value):
        state["mode"] = value
        draw()

    mode_bar = ctk.CTkSegmentedButton(modes, values=list(COMPARE_MODES), command=set_mode, font=(UI_FONT, 14), border_width=0, fg_color=PAD_COLOR, unselected_color="#1f2029", corner_radius=0)
    mode_bar.set(state["mode"])
    ctk.CTkLabel(modes, text="Q", font=(UI_FONT, 16), text_color="grey").grid(row=0, column=0, padx=(0, 8))
    mode_bar.grid(row=0, column=1)
    ctk.CTkLabel(modes, text="E", font=(UI_FONT, 16), text_color="grey").grid(row=0, column=2, padx=(8, 0))
    def key_mode(name):
        def handler(event=None):
            mode_bar.set(name)
            set_mode(name)
            return "break"
        return handler

    def cycle_mode(delta):
        def handler(event=None):
            names = list(COMPARE_MODES)
            name = names[(names.index(state["mode"]) + delta) % len(names)]
            mode_bar.set(name)
            set_mode(name)
            return "break"
        return handler

    def key_step(delta):
        def handler(event=None):
            if state["mode"] == "Blink" and state["label"] is not None:
                state["blink"] = (state["blink"] + delta) % n
                state["label"].configure(image=full_photos[state["blink"]])
                blink_caption()
            elif state["mode"] == "Side by side":
                state["pick"] = (state["pick"] + delta) % n
                draw()
            elif state["mode"] == "Slider":
                state["pair"] += delta
                draw()
            return "break"
        return handler

    def key_keep_shown(event=None):
        if state["mode"] == "Blink":
            choose(kept[state["blink"]])
        elif state["mode"] == "Side by side":
            choose(kept[state["pick"]])
        elif state["mode"] == "Slider":
            choose(kept[state["pair"] % (n - 1)])
        return "break"

    def key_close(event=None):
        compare_close()
        return "break"

    win.bind("<space>", flip)
    win.bind("<Key-0>", side_reset)
    for seq in ("<Escape>", "<Return>", "<KP_Enter>", "<Tab>"):
        win.bind(seq, key_close)
    for number, name in enumerate(COMPARE_MODES, start=1):
        win.bind(f"<Key-{number}>", key_mode(name))
    win.bind("<Left>", key_step(-1))
    win.bind("<Right>", key_step(1))
    for letters, handler in (("qQ", cycle_mode(-1)), ("eE", cycle_mode(1)), ("aA", key_step(-1)), ("dD", key_step(1)), ("kKrR", key_keep_shown)):
        for letter in letters:
            win.bind(f"<{letter}>", handler)
    draw()
    full_begin()
    win.after(300, lambda: set_inspect_icon(win))
    win.after(60, lambda: reveal(win))

def move_journaled(item, destination):
    try:
        with open(journal_name, "a", encoding="utf-8") as f:
            f.write(json.dumps({"from": str(item), "to": str(destination)}) + "\n")
        item.rename(destination)
        return True
    except OSError:
        logging.exception("Could not move %s.", item.name)
        return False

def delete_rest():
    kept, rest = group_kept_files()
    if open_idx is None or open_idx == other_idx or not kept or not rest:
        return
    if execute_button.cget("state") == "disabled":
        messagebox.showinfo("Specorde", "Another task is still running. Try again when it has finished.")
        return
    if not messagebox.askyesno("Specorde", f"Keep {len(kept)}, move {len(rest)} others to '{rejected_name}'?\n\nYou can undo this with 'Restore folder' in Organize.\n\nContinue?"):
        return
    reject_files(rest, kept)

def pictures_open():
    global currently_open
    global pending_pics
    global pics_folder
    global cards
    middle_reset()
    middle.grid_columnconfigure(0, weight=1)
    middle.grid_rowconfigure(8, weight=0)
    middle.grid_rowconfigure(10, weight=1)
    header.grid(column=0, row=0, sticky="ew", pady=(0,16))
    culler_label.grid(sticky="nw", pady=18, padx=18)
    folder_strip.grid(row=0, column=0, columnspan=3, sticky="nw")
    if pics_view == "edit" and ed_view.file is not None:
        ed_focus(True)
        ed_back_button.grid(row=1, column=0, sticky="w", padx=(16, 8), pady=10)
        ed_name_label.configure(text=trim(ed_view.file.name, 60))
        ed_name_label.grid(row=1, column=1, sticky="w", pady=10)
        ed_view.frame.grid(row=1, column=0, sticky="n")
        currently_open = 3
        return
    culler_mode_switch.set("All photos" if pics_mode == "all" else "Groups")
    culler_mode_switch.grid(row=0, column=1, sticky="w")
    header_show()
    if "target_folder" not in globals():
        pending_pics = []
        cards = []
        pics_folder = None
        grid_clear()
        no_folder_label.grid(row=1, pady=20)
    else:
        if target_folder != pics_folder or folder_stamp() != pics_stamp:
            grid_load_folder()
        elif scan_active or copies_active:
            culler_loading.grid(row=1, pady=20)
        else:
            overview_frame.grid(row=1, column=0, sticky="ew")
            cutesy_bar.grid(row=10, column=0, sticky="sew")
            empty_update()
            schedule_refresh()
    currently_open = 3
    bottom_bar_update()

def organize_open():
    global actions_water
    global actions_find
    global actions_sort
    global middle
    global currently_open

    if not currently_open == 0:
        middle_reset()
    
    middle.grid_columnconfigure(2, weight=0)
    middle.grid_rowconfigure(10, weight=1)
    middle.grid_rowconfigure(8, weight=0)
    header.grid(column=0, row=0,sticky="ew", pady=(0,24))
    organize_title.grid(sticky="nw", pady=18, padx=18)
    folder_strip.grid(row=0, column=0, columnspan=3, sticky="nw")
    actions_title.grid(sticky="nw", padx=26, pady=(25,10), row=4)
    actions_find.grid(sticky="nw", padx=32, pady=(5,10), row=5)
    actions_sort.grid(sticky="nw", padx=32, pady=10, row=6)
    actions_rename.grid(sticky="nw", padx=32, pady=10, row=7)
    execute_button.grid(row=9, column=0, padx=104,pady=24)
    footer.grid(row=10, column=0, sticky="sw", padx=0, pady=(0,0))
    file_disclaimer.grid(row=0, column=0, sticky="sw", pady=0, padx=12)
    restore_button.grid(row=0, column=1, sticky="e", padx=(146, 60), pady=6)
    dry_run_button.grid(row=0, column=1, sticky="e", padx=(200, 0), pady=6)
    currently_open = 0 #(0 for organize, 1 for settings, 2 for tutorial)

def settings_open(option=0):
    global currently_open
    middle_reset()
    middle.grid_columnconfigure(0, weight=1)
    middle.grid_rowconfigure(8, weight=1)
    header.grid(column=0, row=0, sticky="ew", pady=(0,16))
    settings_label.grid(sticky="nw", pady=(18,0), padx=18, column=0, row=0)
    settings_org_button.grid(sticky="sw", pady=8, padx=(16,8), column=0, row=1)
    folder_strip.grid(row=0, column=0, columnspan=3, sticky="nw")
    find_explain.grid(row=2, column=0, padx=20, pady=(5,0), sticky="w")
    find_settings.grid(row=3, column=0, padx=20, pady=(1,12), sticky="ew")
    sort_explain.grid(row=4, column=0, padx=20, pady=(5,0), sticky="w")
    sort_settings.grid(row=5, column=0, padx=20, pady=(1,12), sticky="ew")
    rename_explain.grid(row=6, column=0, padx=20, pady=(5,0), sticky="w")
    rename_settings.grid(row=7, column=0, padx=20, pady=(1,12), sticky="ew")
    currently_open = 1

def settings_change(option=0):
    settings_open(option)

def tutorial_open():
    global middle
    global currently_open
    if not currently_open == 2:
        middle_reset()
    middle.grid_columnconfigure(0, weight=1)
    header.grid(column=0, row=0,sticky="ew", pady=(0,24))
    tutorial_label.grid(sticky="nw", pady=18, padx=18)
    folder_strip.grid(row=0, column=0, columnspan=3, sticky="nw")
    tutorial_frame.grid(row=1, column=0, sticky="nw", padx=(18, 6))
    currently_open = 2 #(0 for organize, 1 for settings, 2 for tutorial)

SOFT_RATIO = 0.45
PICK_MARGIN = 1.25
SOFT_MAX_SHARE = 0.5
suggest_busy = False
BEST_COLOR = "#c79a1b"
SOFT_COLOR = "#c8641f"
DONE_COLOR = "#2e8b57"
IDLE_COLOR = "#173348"

def sharp_verdict(scores):
    valid = {f: s for f, s in scores.items() if s is not None}
    if len(valid) < 2:
        return {}, ""
    ranked = sorted(valid.values(), reverse=True)
    best = ranked[0]
    if best <= 0:
        return {}, ""
    best_file = max(valid, key=valid.get)
    logging.debug("Sharpness (relative to best): %s", ", ".join(f"{f.name}={s / best:.2f}" for f, s in valid.items()))
    clear_win = ranked[1] <= 0 or best / ranked[1] >= PICK_MARGIN
    soft = {f for f, s in valid.items() if f != best_file and s < best * SOFT_RATIO}
    if len(soft) > len(valid) * SOFT_MAX_SHARE:
        soft = set()
    tags = {f: "soft" for f in soft}
    if clear_win:
        tags[best_file] = "best"
    if not tags:
        return {}, "no clear winner, all about equally sharp"
    parts = [f"★ Sharpest: {trim(best_file.name, 18)}" if clear_win else "top shots are equally sharp"]
    if soft:
        parts.append(f"{len(soft)} soft")
    return tags, "  ·  ".join(parts)

def best_file_now():
    return next((f for f, tag in suggest_tags.items() if tag == "best"), None)

def suggest_button_update():
    best = best_file_now()
    if open_idx is None or open_idx == other_idx:
        btn_set(culler_suggest_button, text="No clear pick", state="disabled", fg_color=IDLE_COLOR)
    elif suggest_busy:
        btn_set(culler_suggest_button, text="Checking...", state="disabled", fg_color=IDLE_COLOR)
    elif best is None:
        btn_set(culler_suggest_button, text="No clear pick", state="disabled", fg_color=IDLE_COLOR)
    elif str(best) in keep_set:
        btn_set(culler_suggest_button, text="★ Kept", state="disabled", fg_color=DONE_COLOR)
    else:
        btn_set(culler_suggest_button, text="★ Keep sharpest", state="normal", fg_color=BEST_COLOR)

def banner_draw():
    pic_canvas.delete("banner")
    if at_groups():
        return
    if open_idx is None:
        text = f"All photos · {len(cards)} · drag to select · right-click for options"
    else:
        text = group_title(open_idx) + ("  ·  finished ✓" if group_is_done(open_idx) else "") + "  ·  drag to select  ·  right-click for options"
    s = ui_scale()
    pic_canvas.create_text(grid_left * s, grid_top * s / 2, text=text, anchor="w", fill="#9aa0b0", font=(UI_FONT, -round(15 * s)), tags="banner")

def suggest_progress(token, done, total):
    return

def key_suggest():
    if open_idx is None:
        return
    best = best_file_now()
    i = card_index_of(best) if best is not None else None
    if i is None:
        return
    if str(best) not in keep_set:
        keep_flip(i)
    sel_set(i)

def suggest_start(idx):
    global suggest_token, suggest_tags, suggest_busy
    suggest_token += 1
    suggest_tags = {}
    suggest_busy = False
    if idx == other_idx or len(groups[idx]) < 2:
        suggest_button_update()
        banner_draw()
        return
    token = suggest_token
    files = list(groups[idx])
    total = len(files)
    suggest_busy = True
    suggest_button_update()
    banner_draw()

    def work():
        scores = {}
        for number, f in enumerate(files, start=1):
            if token != suggest_token:
                return
            scores[f] = sharp_get(f)
            q.put(("suggest_progress", (token, number, total)))
        tags, note = sharp_verdict(scores)
        q.put(("suggest", (token, tags, note)))

    threading.Thread(target=work, daemon=True).start()

def suggest_apply(token, tags, note):
    global suggest_tags, suggest_busy
    if token != suggest_token or open_idx is None:
        return
    suggest_tags = tags
    suggest_busy = False
    suggest_button_update()
    for i in range(len(cards)):
        if (i, 0) in pic_cells:
            badge_refresh(i)
    banner_draw()
    sel_draw()

def group_open(idx, switching=False):
    global cards
    global pending_pics
    global open_idx
    global saved_top
    global sel_idx
    marq_clear()
    if switching:
        click_cancel()
        inspect_close_all()
        compare_close()
        peek_close()
    else:
        saved_top = pic_canvas.yview()[0]
    open_idx = idx
    cards = [[f] for f in groups[idx]]
    pending_pics = [c[0] for c in cards]
    sel_idx = 0 if sel_visible else None
    culler_info_label.configure(text=group_title(idx))
    header_show()
    groups_show()
    inspect_preload(idx)
    suggest_start(idx)

def group_close(event=None):
    global cards
    global pending_pics
    global open_idx
    global sel_idx
    global suggest_token
    global suggest_tags
    marq_clear()
    if open_idx is None:
        return
    closed = open_idx
    click_cancel()
    inspect_close_all()
    compare_close()
    peek_close()
    suggest_token += 1
    suggest_tags = {}
    open_idx = None
    cards = groups
    pending_pics = [c[0] for c in cards]
    sel_idx = closed if sel_visible else None
    header_show()
    grid_clear()
    grid_update_region(grid_geometry())
    pic_canvas.yview_moveto(saved_top)
    if sel_visible:
        sel_scroll_into_view()
    schedule_refresh()

sel_idx = None
sel_visible = False
keys_window = None

KEY_SECTIONS = [
    ("Moving", [
        ("Move the frame", "Arrows or W A S D"),
        ("Open group or photo", "Space, Enter or Tab"),
    ]),
    ("Culling", [
        ("Keep a photo", "R or K"),
        ("Keep the sharpest", "B"),
        ("Mark group finished", "F"),
        ("Finished + next group", "N"),
        ("Edit the selected photo", "G"),
        ("Select with a rectangle", "Drag (Ctrl adds)"),
        ("Select everything", "Ctrl+A"),
        ("Clear selection", "Esc"),
        ("Previous / next group", "[   ]"),
        ("Compare kept", "C"),
        ("Clear kept", "U"),
        ("Wrap up", "E"),
    ]),
    ("Hold to peek", [
        ("Peek at a photo", "Hold Space, Enter or Tab"),
    ]),
]

def main_focus_later():
    def go():
        try:
            if not inspect_windows and compare_window is None:
                canvas.focus_force()
        except Exception:
            pass
    try:
        canvas.after(40, go)
    except Exception:
        pass

def sel_hide():
    global sel_visible
    sel_visible = False
    pic_canvas.delete("sel")

def sel_draw():
    global sel_idx
    pic_canvas.delete("sel")
    if not sel_visible or sel_idx is None or not cards:
        return
    sel_idx = min(sel_idx, len(cards) - 1)
    rects = stack_rects(sel_idx, grid_geometry())
    left = rects[0][0]
    top = rects[-1][1]
    right = left + rects[0][2]
    bottom = rects[0][1] + rects[0][3]
    pad = 3 * ui_scale()
    pic_canvas.create_rectangle(left - pad, top - pad, right + pad, bottom + pad, outline="#ffd24a", width=3, tags="sel")

def sel_scroll_into_view():
    if sel_idx is None or not cards:
        return
    geo = grid_geometry()
    row = sel_idx // geo["per_row"]
    top = geo["slot0"] + row * geo["pitch"]
    bottom = top + geo["pitch"]
    view_top = pic_canvas.canvasy(0)
    view_h = grid_view_h(geo)
    if top < view_top:
        new_top = 0 if row == 0 else top
    elif bottom > view_top + view_h:
        new_top = bottom - view_h
    else:
        return
    new_top = max(0, min(new_top, pic_total_h - view_h))
    if pic_total_h > view_h:
        pic_canvas.yview_moveto(new_top / pic_total_h)
    schedule_refresh()

def sel_set(idx):
    global sel_idx, sel_visible
    if not cards:
        return
    sel_visible = True
    sel_idx = max(0, min(len(cards) - 1, idx))
    hover_clear()
    sel_scroll_into_view()
    sel_draw()

def key_ok():
    if currently_open != 3 or "target_folder" not in globals() or scan_active or copies_active:
        return False
    try:
        focus = canvas.focus_get()
    except Exception:
        focus = None
    return not isinstance(focus, (tk.Entry, tk.Text))

def next_undone(start):
    n = len(groups)
    for step in range(1, n + 1):
        i = (start + step) % n
        if i != start and i != other_idx and not group_is_done(i):
            return i
    return None

def key_default_index():
    if at_groups():
        i = next_undone(-1)
        return i if i is not None else 0
    best = next((f for f, tag in suggest_tags.items() if tag == "best"), None)
    i = card_index_of(best) if best is not None else None
    return i if i is not None else 0

def key_move(delta):
    if not cards:
        return
    if not sel_visible or sel_idx is None:
        sel_set(sel_idx if sel_idx is not None else key_default_index())
    else:
        sel_set(sel_idx + delta)

def key_edge(last):
    if cards:
        sel_set(len(cards) - 1 if last else 0)

def key_page(direction):
    if not cards:
        return
    if not sel_visible or sel_idx is None:
        sel_set(key_default_index())
        return
    geo = grid_geometry()
    rows = max(1, int(grid_view_h(geo) // geo["pitch"]))
    sel_set(sel_idx + direction * rows * geo["per_row"])

def key_open():
    if not cards:
        return
    if not sel_visible or sel_idx is None:
        sel_set(key_default_index())
    if sel_idx is None:
        return
    if at_groups():
        group_open(sel_idx)
    else:
        inspect_show(sel_idx)

def key_back():
    if marq_sel:
        marq_clear()
    elif open_idx is not None:
        group_close()
    else:
        sel_hide()

def key_keep():
    if marq_sel:
        marq_keep(not all(str(f) in keep_set for f in marq_sel))
        return
    if at_groups() or not cards:
        return
    if not sel_visible or sel_idx is None:
        sel_set(key_default_index())
        return
    keep_flip(sel_idx)

def key_unkeep():
    if open_idx is not None:
        clear_kept()

def key_done():
    if pics_mode == "all": return
    idx = open_idx if open_idx is not None else sel_idx
    if idx is None or idx == other_idx or idx >= len(groups):
        return
    done_set_group(idx, not group_is_done(idx))
    if open_idx is None:
        if (idx, 0) in pic_cells:
            badge_refresh(idx)
    else:
        banner_draw()

def key_next():
    if pics_mode == "all": return
    if not groups:
        return
    if open_idx is not None:
        current = open_idx
        kept, _ = group_kept_files()
        if kept and current != other_idx:
            done_set_group(current, True)
        target = next_undone(current)
        if target is None:
            group_close()
            return
        group_open(target, switching=True)
    else:
        target = next_undone(sel_idx if sel_idx is not None else -1)
        if target is not None:
            sel_set(target)

def key_compare():
    if open_idx is None:
        return
    kept, _ = group_kept_files()
    if 2 <= len(kept) <= 4:
        compare_open()

def key_group_step(delta):
    if open_idx is None:
        return
    i = open_idx + delta
    while 0 <= i < len(groups) and i == other_idx:
        i += delta
    if 0 <= i < len(groups):
        group_open(i, switching=True)


def key_finish():
    if open_idx is None:
        finish_open()

def keys_close(event=None):
    global keys_window
    if keys_window is not None:
        try:
            keys_window.destroy()
        except Exception:
            pass
        keys_window = None
    main_focus_later()

def keys_open(event=None):
    global keys_window
    if keys_window is not None:
        keys_close()
        return
    win = ctk.CTkToplevel(canvas)
    win.withdraw()
    win.title("Keyboard shortcuts")
    win.configure(fg_color="#1f2029")
    win.resizable(False, False)
    win.transient(canvas)
    win.protocol("WM_DELETE_WINDOW", keys_close)
    keys_window = win
    ctk.CTkLabel(win, text="Keyboard shortcuts", font=(UI_FONT, 26)).grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(16, 4))
    row = 1
    for title, lines in KEY_SECTIONS:
        ctk.CTkLabel(win, text=title, font=(UI_FONT, 17), text_color="grey").grid(row=row, column=0, columnspan=2, sticky="w", padx=20, pady=(10, 2))
        row += 1
        for action, keys in lines:
            ctk.CTkLabel(win, text=action, font=(UI_FONT, 15), anchor="w").grid(row=row, column=0, sticky="w", padx=(20, 16), pady=2)
            ctk.CTkLabel(win, text=f"  {keys}  ", font=(UI_FONT, 15), fg_color="#2c3043", corner_radius=6).grid(row=row, column=1, sticky="e", padx=(0, 20), pady=2)
            row += 1
    ctk.CTkLabel(win, text="Press any key to close", font=(UI_FONT, 13), text_color="grey").grid(row=row, column=0, columnspan=2, pady=(12, 16))
    win.bind("<Key>", keys_close)
    center_on_main(win)
    win.after(300, lambda: set_inspect_icon(win))
    win.after(60, lambda: reveal(win))

hold_keys = {"tab", "return", "kp_enter", "space", "k", "r"}
key_held = {}

def key_tap(key):
    if key in ("k", "r"):
        key_keep()
    else:
        key_open()

def key_peek_start(key):
    global peek_window
    key_held[key] = "peek"
    if sel_idx is None or sel_idx >= len(cards):
        return
    img = inspect_load(cards[sel_idx][0])
    if img is None:
        return
    peek_close()
    hover_clear()
    photo = ImageTk.PhotoImage(img)
    win = tk.Toplevel(canvas)
    win.overrideredirect(True)
    win.configure(bg=card_edge)
    win.withdraw()
    label = tk.Label(win, image=photo, bd=0, bg="#101117")
    label.image = photo
    label.pack(padx=3, pady=3)
    place_at_mouse(win, canvas.winfo_x() + canvas.winfo_width() // 2, canvas.winfo_y() + canvas.winfo_height() // 2)
    win.deiconify()
    win.attributes("-topmost", True)
    peek_window = win

def key_release(event):
    key = event.keysym.lower()
    job = key_held.pop(key, None)
    if job is None:
        return
    if job == "peek":
        peek_close()
        return "break"
    if job == "done":
        return
    canvas.after_cancel(job)
    key_tap(key)
    return "break"

def key_reset(event=None):
    if event is not None and event.widget is not canvas:
        return
    for job in key_held.values():
        if job not in ("peek", "done"):
            try:
                canvas.after_cancel(job)
            except Exception:
                pass
    key_held.clear()
    peek_close()

def focus_in_text():
    try:
        focus = canvas.focus_get()
    except Exception:
        return False
    return isinstance(focus, (tk.Entry, tk.Text))

def menu_cycle(menu, command=None):
    values = list(menu.cget("values"))
    if not values:
        return
    current = menu.get()
    position = values.index(current) if current in values else -1
    new = values[(position + 1) % len(values)]
    menu.set(new)
    if command:
        command(new)

def ready():
    return execute_button.cget("state") != "disabled"

def page_key(event):
    key = event.keysym.lower()
    if currently_open == 0:
        if key == "1":
            actions_find.toggle()
        elif key == "2":
            actions_sort.toggle()
        elif key == "3":
            actions_rename.toggle()
        elif key in ("return", "kp_enter") and ready():
            run_execute()
        elif key == "p" and ready():
            dry_run_toggle()
        elif key == "r" and ready():
            restore_click()
        elif key == "o" and ready():
            pick_folder()
        else:
            return
    else:
        if key == "d":
            menu_cycle(settings_duplicate_delete)
        elif key == "s":
            menu_cycle(settings_sort_sortby)
        elif key == "t":
            menu_cycle(settings_sort_structure)
        elif key == "n":
            menu_cycle(settings_rename_pattern, rename_pattern_changed)
        elif key == "b" and settings_rename_renameby.winfo_ismapped():
            menu_cycle(settings_rename_renameby)
        else:
            return
    return "break"

def key_press(event):
    if event.state & 0x20004:
        return
    if currently_open in (0, 1):
        if focus_in_text():
            return
        return page_key(event)
    if currently_open == 3 and pics_view == "edit":
        return editor_key(event)
    if not key_ok():
        return
    key = event.keysym.lower()
    shift = bool(event.state & 0x1)
    per_row = grid_geometry()["per_row"]
    if key in hold_keys and not (key == "tab" and shift):
        if key in key_held:
            return "break"
        if not sel_visible or sel_idx is None:
            key_held[key] = "done"
            key_tap(key)
        else:
            key_held[key] = canvas.after(hold_ms, lambda k=key: key_peek_start(k))
        return "break"
    if key in ("left", "a"):
        key_move(-1)
    elif key in ("right", "d"):
        key_move(1)
    elif key in ("up", "w"):
        key_move(-per_row)
    elif key in ("down", "s"):
        key_move(per_row)
    elif key == "home":
        key_edge(False)
    elif key == "end":
        key_edge(True)
    elif key == "prior":
        key_page(-1)
    elif key == "next":
        key_page(1)
    elif key == "iso_left_tab" or (key == "tab" and shift):
        key_back()
    elif key in ("return", "kp_enter", "tab", "space"):
        key_open()
    elif key in ("escape", "backspace"):
        key_back()
    elif key in ("k", "r"):    
        key_keep()
    elif key == "b":
        key_suggest()
    elif key == "f":
        key_done()
    elif key == "n":
        key_next()
    elif key == "bracketleft":
        key_group_step(-1)
    elif key == "bracketright":
        key_group_step(1)
    elif key == "c":
        key_compare()
    elif key == "u":
        key_unkeep()
    elif key == "e":
        key_finish()
    elif key == "g":
        key_edit()
    elif key in ("f1", "question"):
        keys_open()
    else:
        return
    return "break"

inspect_state = {}

def inspect_caption(file):
    return file.name

def inspect_close(win):
    if win in inspect_windows:
        inspect_windows.remove(win)
    for key in [k for k, v in inspect_by_file.items() if v is win]:
        del inspect_by_file[key]
        inspect_buttons.pop(key, None)
    inspect_state.pop(win, None)
    try:
        win.destroy()
    except Exception:
        pass
    main_focus_later()

def inspect_fill(win, file, img):
    st = inspect_state[win]
    old = st["file"]
    if old is not None:
        inspect_by_file.pop(old, None)
        inspect_buttons.pop(old, None)
    photo = ImageTk.PhotoImage(img)
    st["label"].configure(image=photo)
    st["label"].image = photo
    st["caption"].configure(text=inspect_caption(file))
    st["button"].configure(text=keep_text(file))
    st["file"] = file
    inspect_by_file[file] = win
    inspect_buttons[file] = st["button"]
    try:
        win.title(file.name)
    except Exception:
        pass

def inspect_recenter(win, cx, cy):
    try:
        win.update_idletasks()
        w = win.winfo_reqwidth()
        h = win.winfo_reqheight()
        left, top, right, bottom = monitor_area(cx, cy)
        px = min(max(cx - w // 2, left), max(right - w, left))
        py = min(max(cy - h // 2, top), max(bottom - h, top))
        tk.Wm.geometry(win, f"+{px}+{py}")
    except Exception:
        logging.exception("Could not recentre the photo window.")

def inspect_keep(win):
    st = inspect_state.get(win)
    if st is None or st["file"] is None:
        return
    lock_toggle(st["file"])
    keep_refresh(st["file"])

def inspect_prefetch(center):
    box = inspect_box()
    files = [cards[i][0] for i in (center + 1, center - 1, center + 2) if 0 <= i < len(cards)]

    def work():
        for f in files:
            inspect_load(f, box)

    threading.Thread(target=work, daemon=True).start()

def inspect_step(win, delta):
    st = inspect_state.get(win)
    if st is None or at_groups():
        return
    current = card_index_of(st["file"])
    if current is None:
        return
    new = current + delta
    if not 0 <= new < len(cards):
        return
    target = cards[new][0]
    other = inspect_by_file.get(target)
    if other is not None and other is not win:
        try:
            if other.winfo_exists():
                other.lift()
                other.focus_force()
                return
        except Exception:
            pass
    img = inspect_load(target)
    if img is None:
        return
    inspect_fill(win, target, img)
    inspect_recenter(win, st["cx"], st["cy"])
    sel_set(new)
    inspect_prefetch(new)

def inspect_show(idx, x=None, y=None):
    if idx >= len(cards):
        return
    file = cards[idx][0]
    existing = inspect_by_file.get(file)
    if existing is not None:
        try:
            if existing.winfo_exists():
                existing.lift()
                existing.focus_force()
                return
        except Exception:
            pass
    img = inspect_load(file)
    if img is None:
        return
    hover_clear()

    win = ctk.CTkToplevel(canvas)
    win.withdraw()
    win.configure(fg_color="#101117")
    win.resizable(False, False)
    win.transient(canvas)
    win.protocol("WM_DELETE_WINDOW", lambda: inspect_close(win))

    frame = tk.Frame(win, bg="#101117", highlightbackground=card_edge, highlightthickness=2, bd=0)
    frame.grid(row=0, column=0, padx=14, pady=(14, 6))
    label = tk.Label(frame, bd=0, bg="#101117", cursor="hand2")
    label.grid(padx=5, pady=5)
    label.bind("<ButtonRelease-1>", lambda e: inspect_close(win))
    caption = tk.Label(win, text="", bg="#101117", fg="#c8ccd8", font=(UI_FONT, 12))
    caption.grid(row=1, column=0)
    keep_button = ctk.CTkButton(win, text="Keep", command=lambda: inspect_keep(win), font=(UI_FONT, 16), width=120, height=30)
    keep_button.grid(row=2, column=0, pady=(8, 6))
    ctk.CTkButton(win, text="Edit", command=lambda: edit_from_inspect(win), font=(UI_FONT, 16), width=120, height=30).grid(row=3, column=0, pady=(0, 12))
    inspect_state[win] = {"file": None, "label": label, "caption": caption, "button": keep_button, "cx": 0, "cy": 0}
    inspect_fill(win, file, img)

    held = set()

    def on_key(event):
        key = event.keysym.lower()
        if key in ("left", "up", "a", "w", "right", "down", "d", "s"):
            inspect_step(win, -1 if key in ("left", "up", "a", "w") else 1)
            return "break"
        if key in held:
            return "break"
        if key in ("return", "kp_enter", "escape", "tab", "space"):
            inspect_close(win)
        elif key in ("k", "r"):
            held.add(key)
            inspect_keep(win)
        elif key == "g":
            edit_from_inspect(win)
        return "break"

    def on_release(event):
        held.discard(event.keysym.lower())

    win.bind("<KeyPress>", on_key)
    win.bind("<KeyRelease>", on_release)

    offset = 28 * len(inspect_windows)
    inspect_windows.append(win)
    if x is None:
        center_on_main(win, offset)
        anchor_x = canvas.winfo_x() + canvas.winfo_width() // 2 + offset
        anchor_y = canvas.winfo_y() + canvas.winfo_height() // 2 + offset
    else:
        place_at_mouse(win, x, y)
        anchor_x, anchor_y = x, y
    inspect_state[win]["cx"] = anchor_x
    inspect_state[win]["cy"] = anchor_y
    win.after(300, lambda: set_inspect_icon(win))
    win.after(60, lambda: reveal(win))
    inspect_prefetch(idx)

kept_name = "kept_specorde"
finish_window = None

def finish_plans():
    plans = []
    skipped = 0
    for i, g in enumerate(groups):
        if i == other_idx or not group_is_done(i):
            continue
        kept = [f for f in g if str(f) in keep_set]
        rest = [f for f in g if str(f) not in keep_set]
        if kept and rest:
            plans.append((kept, rest))
        elif not kept:
            skipped += 1
    return plans, skipped

def kept_now():
    folder = str(target_folder)
    return [Path(k) for k in sorted(keep_set) if os.path.dirname(k) == folder and os.path.isfile(k)]

def finish_close(event=None):
    global finish_window
    if finish_window is not None:
        try:
            finish_window.destroy()
        except Exception:
            pass
        finish_window = None
    main_focus_later()

def finish_open(event=None):
    global finish_window
    if open_idx is not None or scan_active or copies_active or "target_folder" not in globals():
        return
    if finish_window is not None:
        finish_close()
        return
    plans, skipped = finish_plans()
    n_groups = len(plans)
    n_rest = sum(len(r) for _, r in plans)
    kept = kept_now()
    folder = target_folder / kept_name

    win = ctk.CTkToplevel(canvas)
    win.withdraw()
    win.title("Wrap up culling")
    win.configure(fg_color="#1f2029")
    win.resizable(False, False)
    win.transient(canvas)
    win.protocol("WM_DELETE_WINDOW", finish_close)
    finish_window = win

    def do_reject():
        finish_close()
        apply_done(plans)

    def do_collect():
        finish_close()
        collect_kept(kept)

    def do_open():
        try:
            os.startfile(str(folder))
        except Exception:
            logging.exception("Could not open the kept folder.")

    ctk.CTkLabel(win, text="Wrap up culling", font=(UI_FONT, 26)).grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(16, 0))
    ctk.CTkLabel(win, text="Only groups you marked finished (F or N) are touched.", font=(UI_FONT, 13), text_color="grey").grid(row=1, column=0, columnspan=2, sticky="w", padx=20, pady=(0, 10))

    reject_text = f"{n_rest} not-kept photo{'' if n_rest == 1 else 's'} in {n_groups} finished group{'' if n_groups == 1 else 's'}"
    ctk.CTkLabel(win, text=reject_text, font=(UI_FONT, 16), anchor="w").grid(row=2, column=0, sticky="w", padx=(20, 16), pady=6)
    ctk.CTkButton(win, text=f"Move to {rejected_name}", command=do_reject, font=(UI_FONT, 14), width=210, height=28, state="normal" if plans else "disabled", fg_color="#8b2e2e" if plans else "#173348").grid(row=2, column=1, padx=(0, 20), pady=6)

    collect_text = f"{len(kept)} kept photo{'' if len(kept) == 1 else 's'}"
    ctk.CTkLabel(win, text=collect_text, font=(UI_FONT, 16), anchor="w").grid(row=3, column=0, sticky="w", padx=(20, 16), pady=6)
    ctk.CTkButton(win, text=f"Copy to {kept_name}", command=do_collect, font=(UI_FONT, 14), width=210, height=28, state="normal" if kept else "disabled", fg_color="#1f6aa5" if kept else "#173348").grid(row=3, column=1, padx=(0, 20), pady=6)

    row = 4
    if skipped:
        ctk.CTkLabel(win, text=f"{skipped} finished group{'' if skipped == 1 else 's'} with nothing kept {'is' if skipped == 1 else 'are'} left alone.", font=(UI_FONT, 13), text_color="grey").grid(row=row, column=0, columnspan=2, sticky="w", padx=20, pady=(2, 0))
        row += 1
    if folder.is_dir():
        ctk.CTkButton(win, text=f"Open {kept_name}", command=do_open, font=(UI_FONT, 13), width=150, height=24).grid(row=row, column=0, columnspan=2, sticky="w", padx=20, pady=(10, 0))
        row += 1
    ctk.CTkLabel(win, text="Moving can be undone with 'Restore folder'. Copies are not removed by it.", font=(UI_FONT, 12), text_color="grey").grid(row=row, column=0, columnspan=2, sticky="w", padx=20, pady=(10, 4))
    ctk.CTkButton(win, text="Close", command=finish_close, font=(UI_FONT, 14), width=90, height=24).grid(row=row + 1, column=0, columnspan=2, sticky="e", padx=20, pady=(4, 16))
    win.bind("<Escape>", finish_close)
    center_on_main(win)
    win.after(300, lambda: set_inspect_icon(win))
    win.after(60, lambda: reveal(win))

def reject_files(rest, kept):
    global journal_name, pics_stamp, scan_order, sel_idx
    global suggest_token, suggest_tags
    rejected = target_folder / rejected_name
    journal_name = journal_path / f"run_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')}.jsonl"
    try:
        journal_path.mkdir(parents=True, exist_ok=True)
        with open(journal_name, "x", encoding="utf-8") as f:
            f.write(json.dumps({"folder": str(target_folder)}) + "\n")
        rejected.mkdir(exist_ok=True)
    except OSError:
        logging.exception("Could not prepare the rejected folder.")
        messagebox.showwarning("Specorde", "Could not create the rejected folder.")
        return
    moved_files = []
    failed = 0
    for file in rest:
        destination = rejected / file.name
        counter = 1
        while destination.exists():
            destination = rejected / f"{file.stem}_{counter}{file.suffix}"
            counter += 1
        if move_journaled(file, destination):
            moved_files.append(file)
        else:
            failed += 1
    if not moved_files:
        try:
            journal_name.unlink()
        except OSError:
            pass
    logging.info("Culler: kept %d, moved %d to %s, %d failed.", len(kept), len(moved_files), rejected_name, failed)
    gone = set(moved_files)
    scan_order = [f for f in scan_order if f not in gone]
    for f in moved_files:
        photo_info.pop(f, None)
    pics_stamp = folder_stamp()
    done_set.update(str(f) for f in kept)
    done_save()
    suggest_token += 1
    suggest_tags = {}
    sel_idx = None
    inspect_close_all()
    compare_close()
    groups_build()
    groups_log()
    header_show()
    groups_show()
    text = f"✓ {len(moved_files)} photo{'' if len(moved_files) == 1 else 's'} moved to rejected."
    if failed:
        text = f"✗ {len(moved_files)} moved, {failed} failed."
    q.put(("summary_add", text))
    q.put(("summary_hide_later", None))

def apply_done(plans):
    if not plans:
        return
    if execute_button.cget("state") == "disabled":
        messagebox.showinfo("Specorde", "Another task is still running. Try again when it has finished.")
        return
    rest = [f for _, r in plans for f in r]
    kept = [f for k, _ in plans for f in k]
    n = len(plans)
    if not messagebox.askyesno("Specorde", f"Keep {len(kept)} and move {len(rest)} other photos from {n} finished group{'' if n == 1 else 's'} to '{rejected_name}'?\n\nOne 'Restore folder' in Organize puts all of them back.\n\nContinue?"):
        return
    reject_files(rest, kept)

def collect_work(files, folder):
    q.put(("lock", None))
    q.put(("summary_clear", None))
    q.put(("bar_show", None))
    q.put(("bar_text_show", None))
    copied = 0
    skipped = 0
    failed = 0
    try:
        folder.mkdir(exist_ok=True)
        sizes_list = []
        for f in files:
            try:
                sizes_list.append(f.stat().st_size)
            except OSError:
                sizes_list.append(0)
        total = sum(sizes_list) or 1
        done = 0
        bar_start()
        for f, file_size in zip(files, sizes_list):
            done += file_size
            progress("Collecting kept...", done, total)
            try:
                destination = folder / f.name
                if destination.exists() and destination.stat().st_size == file_size:
                    skipped += 1
                    continue
                counter = 1
                while destination.exists():
                    destination = folder / f"{f.stem}_{counter}{f.suffix}"
                    counter += 1
                shutil.copy2(f, destination)
                copied += 1
            except OSError:
                logging.exception("Could not copy %s.", f.name)
                failed += 1
    except Exception:
        logging.exception("Collecting kept photos failed.")
        failed += 1
    finally:
        logging.info("Collected kept photos: %d copied, %d already there, %d failed.", copied, skipped, failed)
        text = f"✓ {copied} photo{'' if copied == 1 else 's'} copied to {kept_name}."
        if skipped:
            text += f" {skipped} already there."
        if failed:
            text = f"✗ {copied} copied, {failed} failed."
        q.put(("bar_set", 1))
        q.put(("bar_text", "100%"))
        q.put(("summary_add", text))
        q.put(("summary_hide_later", None))
        q.put(("status", "Kept photos collected!" if not failed else "Collected with errors. See log."))
        q.put(("status_reset", None))
        q.put(("bar_text_destroy", None))
        q.put(("bar_destroy", None))
        q.put(("unlock", None))

def collect_kept(files):
    if not files:
        return
    if execute_button.cget("state") == "disabled":
        messagebox.showinfo("Specorde", "Another task is still running. Try again when it has finished.")
        return
    n = len(files)
    if not messagebox.askyesno("Specorde", f"Copy {n} kept photo{'' if n == 1 else 's'} to '{kept_name}'?\n\nYour originals stay where they are. 'Restore folder' does not remove these copies.\n\nContinue?"):
        return
    lock_ui()
    folder = target_folder / kept_name
    start_execute(lambda: collect_work(files, folder))

#======================================================= EDITOR
ED_HUES = (("Red", (1.0, 0.25, 0.2)), ("Orange", (1.0, 0.6, 0.2)), ("Yellow", (1.0, 0.9, 0.3)), ("Green", (0.3, 0.85, 0.4)), ("Teal", (0.2, 0.8, 0.8)), ("Blue", (0.3, 0.5, 1.0)), ("Purple", (0.6, 0.35, 0.95)), ("Pink", (1.0, 0.45, 0.75)))
ED_LOOK = ("exposure", "brilliance", "highlights", "shadows", "contrast", "blackpoint", "fade", "saturation", "vibrancy", "warmth", "tint", "hue_amount", "sharpness", "definition", "noise", "vignette", "tilt", "tilt_pos")
ED_DEFAULT = {"turns": 0, "flip_h": False, "flip_v": False, "angle": 0.0, "crop": None, "hue": 0}
ED_DEFAULT.update({k: 0.0 for k in ED_LOOK})
ED_DEFAULT.update({"wm_on": False, "wm_corner": "Bottom Right", "wm_size": 20.0, "auto": False})
ED_GROUPS = (
    ("Light", (("exposure", "Exposure", -1.0, 1.0), ("brilliance", "Brilliance", -1.0, 1.0), ("highlights", "Highlights", -1.0, 1.0), ("shadows", "Shadows", -1.0, 1.0), ("contrast", "Contrast", -1.0, 1.0), ("blackpoint", "Black point", -1.0, 1.0), ("fade", "Fade", 0.0, 1.0))),
    ("Colour", (("saturation", "Saturation", -1.0, 1.0), ("vibrancy", "Vibrancy", -1.0, 1.0), ("warmth", "Warmth", -1.0, 1.0), ("tint", "Tint", -1.0, 1.0), ("hue_amount", "Colour wash", 0.0, 1.0))),
    ("Detail", (("sharpness", "Sharpness", 0.0, 1.0), ("definition", "Definition", -1.0, 1.0), ("noise", "Noise reduction", 0.0, 1.0))),
    ("Effects", (("vignette", "Vignette", -1.0, 1.0), ("tilt", "Tilt shift", 0.0, 1.0), ("tilt_pos", "Tilt position", -1.0, 1.0))),
)
ED_RATIOS = {"Free": None, "Original": "orig", "1:1": 1.0, "4:5": 4 / 5, "5:4": 5 / 4, "3:2": 3 / 2, "2:3": 2 / 3, "16:9": 16 / 9, "9:16": 9 / 16}
ED_SAVE_FORMATS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP", ".tif": "TIFF", ".tiff": "TIFF", ".bmp": "BMP"}
ED_FOLDER = "edited_specorde"
ED_PRESET_HINT = "Choose a look..."
ED_BUILTIN = {
    "Normal": {},
    "Vivid": {"vibrancy": 0.5, "saturation": 0.15, "contrast": 0.2, "definition": 0.3, "sharpness": 0.25},
    "Warm glow": {"warmth": 0.4, "exposure": 0.1, "fade": 0.2, "highlights": -0.2, "tint": 0.1},
    "Cool": {"warmth": -0.4, "tint": -0.1, "contrast": 0.1, "saturation": -0.05},
    "Faded film": {"fade": 0.55, "contrast": -0.15, "saturation": -0.2, "warmth": 0.15, "vignette": 0.25},
    "Punchy": {"contrast": 0.4, "blackpoint": 0.3, "definition": 0.4, "vibrancy": 0.3, "shadows": 0.15},
    "Mono": {"saturation": -1.0, "contrast": 0.3, "definition": 0.3, "vignette": 0.2},
    "Soft dream": {"brilliance": 0.3, "fade": 0.25, "definition": -0.3, "warmth": 0.15, "highlights": -0.15},
    "Miniature": {"tilt": 0.6, "saturation": 0.3, "contrast": 0.15, "sharpness": 0.3},
}
presets_file = path / "presets.json"

def ed_presets_load():
    try:
        with open(presets_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): v for k, v in data.items() if isinstance(v, dict)}

ed_presets = ed_presets_load()

def ed_presets_save():
    tmp = presets_file.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(ed_presets, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, presets_file)
    except OSError:
        logging.exception("Could not save the presets.")

def ed_copy(st):
    out = dict(st)
    out["crop"] = list(st["crop"]) if st["crop"] else None
    return out

def ed_background(w, h):
    gradient = Image.linear_gradient("L").resize((w, h), Image.BILINEAR)
    return ImageOps.colorize(gradient, black="#1c1e2b", white="#0f1017")

def ed_look_active(st):
    return any(abs(st[k]) > 0.001 for k in ED_LOOK)

def ed_lum(a):
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114

def ed_box_blur(a, r):
    k = 2 * r + 1
    p = np.pad(a, r, mode="edge")
    c = np.pad(p.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)

# ---- batch-aware prep: sleeve finding, square crop window, colour matching ----
ED_PREP_MARGIN = 1.10      # how much floor shows around the sleeve (1.10 = 5% each side)
ED_PREP_WHITE = 0.92       # brightness the batch's highlights are lifted to (one shared lift)

def ed_blob(mask):
    # biggest solid region of a True/False picture, found on a coarse grid (fast); returns (box in pixels, how full the box is)
    step = max(1, mask.shape[1] // 160)
    cells = Image.fromarray((mask * 255).astype(np.uint8)).resize((max(1, mask.shape[1] // step), max(1, mask.shape[0] // step)), Image.BOX)
    cells = cells.point([0] * 128 + [255] * 128)
    cells = cells.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.MinFilter(7))
    cells = cells.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5))
    grid = np.asarray(cells) > 127
    h, w = grid.shape
    seen = np.zeros_like(grid)
    best = None
    for sy in range(h):
        for sx in range(w):
            if grid[sy, sx] and not seen[sy, sx]:
                todo = deque([(sy, sx)])
                seen[sy, sx] = True
                found = []
                while todo:
                    y, x = todo.popleft()
                    found.append((y, x))
                    for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                        if 0 <= ny < h and 0 <= nx < w and grid[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            todo.append((ny, nx))
                if best is None or len(found) > len(best):
                    best = found
    if not best or len(best) < 20:
        return None
    ys = np.array([c[0] for c in best])
    xs = np.array([c[1] for c in best])
    box_w = xs.max() - xs.min() + 1
    box_h = ys.max() - ys.min() + 1
    return (xs.min() * step, ys.min() * step, min((xs.max() + 1) * step, mask.shape[1]), min((ys.max() + 1) * step, mask.shape[0])), len(best) / (box_w * box_h)

def ed_saturation(a):
    mx = a.max(axis=2)
    return float((mx - a.min(axis=2)).mean() / max(float(mx.mean()), 0.02))

def ed_sleeve_find(img):
    small = img.convert("RGB")
    small.thumbnail((640, 640))
    a = np.asarray(small, np.float32)
    h, w = a.shape[:2]
    gray = a @ np.array([0.299, 0.587, 0.114], np.float32)
    spread = np.sqrt(np.maximum(ed_box_blur(gray * gray, 4) - ed_box_blur(gray, 4) ** 2, 0))
    smooth = spread < 4.0
    blurred = np.asarray(small.filter(ImageFilter.GaussianBlur(3)), np.float32)
    edge = np.concatenate([blurred[:6].reshape(-1, 3), blurred[-6:].reshape(-1, 3), blurred[:, :6].reshape(-1, 3), blurred[:, -6:].reshape(-1, 3)])
    dist = np.abs(blurred - np.median(edge, axis=0)).sum(axis=2)
    cut = max(ed_otsu(dist.ravel()), 25.0)
    colour = dist > cut
    best = None
    for mask in (colour, smooth, colour | smooth):
        found = ed_blob(mask)
        if found is None:
            continue
        (x0, y0, x1, y1), fill = found
        bw, bh = x1 - x0, y1 - y0
        area = bw * bh / (w * h)
        # a sleeve can fill almost the whole frame; only tiny bits and "the whole picture" are junk
        if area > 0.99 or area < 0.12:
            continue
        squareness = min(bw, bh) / max(bw, bh)
        score = fill * 0.5 + squareness * 0.3 + min(area / 0.5, 1.0) * 0.2
        if best is None or score > best[0]:
            best = (score, (x0 / w, y0 / h, x1 / w, y1 / h))
    return best[1] if best else None

def ed_edge_step(a, side, x0, y0, x1, y1):
    # 0..1: how sharp the picture changes across one side of the box (a real sleeve edge is sharp)
    h, w = a.shape[:2]
    band = max(3, int(0.02 * min(h, w)))
    if side == "top":
        if y0 - band < 0:
            return 0.0
        out, inn, axis = a[y0 - band:y0, x0:x1], a[y0:y0 + band, x0:x1], 0
    elif side == "bottom":
        if y1 + band > h:
            return 0.0
        out, inn, axis = a[y1:y1 + band, x0:x1], a[y1 - band:y1, x0:x1], 0
    elif side == "left":
        if x0 - band < 0:
            return 0.0
        out, inn, axis = a[y0:y1, x0 - band:x0], a[y0:y1, x0:x0 + band], 1
    else:
        if x1 + band > w:
            return 0.0
        out, inn, axis = a[y0:y1, x1:x1 + band], a[y0:y1, x1 - band:x1], 1
    if out.size == 0 or inn.size == 0:
        return 0.0
    m_out, m_in = out.mean(axis=axis), inn.mean(axis=axis)
    step = np.abs(m_out - m_in).sum(axis=-1) / (m_out.sum(axis=-1) + m_in.sum(axis=-1) + 0.1)
    return float((step > 0.2).mean())

def ed_square_window(img, box, margin=ED_PREP_MARGIN):
    # square crop around the box, as (centre x, centre y, side) in fractions of the width / height / width
    small = img.convert("RGB")
    small.thumbnail((640, 640))
    a = np.asarray(small, np.float32) / 255
    h, w = a.shape[:2]
    x0, y0, x1, y1 = round(box[0] * w), round(box[1] * h), round(box[2] * w), round(box[3] * h)
    bw, bh = x1 - x0, y1 - y0
    side = min(max(bw, bh) * margin, w, h)
    steps = {s: ed_edge_step(a, s, x0, y0, x1, y1) for s in ("top", "bottom", "left", "right")}
    def place(lo, hi, limit, first, second):
        # the sleeve is square, so the shorter way is where the detector most likely missed a bit:
        # hold on to the side with the sharper edge and let the window grow from there
        pad = side * (margin - 1) / 2
        if hi - lo >= side - 1e-6:
            start = (lo + hi) / 2 - side / 2
        elif steps[first] > steps[second] + 0.15:
            start = lo - pad
        elif steps[second] > steps[first] + 0.15:
            start = hi + pad - side
        else:
            start = (lo + hi) / 2 - side / 2
        return min(max(start, 0), limit - side)
    left = place(x0, x1, w, "left", "right")
    top = place(y0, y1, h, "top", "bottom")
    return ((left + side / 2) / w, (top + side / 2) / h, side / w)

def ed_floor_colour(img, box):
    small = img.convert("RGB")
    small.thumbnail((320, 320))
    a = np.asarray(small, np.float32) / 255
    h, w = a.shape[:2]
    keep = np.ones((h, w), bool)
    pad = 0.03
    x0, y0, x1, y1 = box
    keep[max(int((y0 - pad) * h), 0):int((y1 + pad) * h) + 1, max(int((x0 - pad) * w), 0):int((x1 + pad) * w) + 1] = False
    if keep.mean() < 0.08:
        return None
    return np.median(a[keep], axis=0)

def ed_plan(files):
    lw = np.array([0.299, 0.587, 0.114])
    items = []
    for file in files:
        img = load_image(file, (640, 640))
        box = ed_sleeve_find(img)
        window = ed_square_window(img, box) if box else None
        floor = ed_floor_colour(img, box) if box else None
        a = np.asarray(img.convert("RGB"), np.float32) / 255
        items.append({"file": file, "window": window, "floor": floor,
                      "peak": max(float(np.percentile(a.max(axis=2), 99.5)), 0.05),
                      "med": max(float(np.median(a @ lw)), 0.02), "sat": ed_saturation(a)})
    seen = [i for i in items if i["floor"] is not None]
    if len(seen) >= 3:
        # a "floor" far darker or brighter than the rest is probably the sleeve itself, so it must not set the reference
        mid = float(np.median([i["floor"] @ lw for i in seen]))
        for i in seen:
            if not 0.45 < float(i["floor"] @ lw) / max(mid, 0.01) < 2.2:
                i["floor"] = None
    floors = np.array([i["floor"] for i in items if i["floor"] is not None])
    if len(floors) > 0:
        ref = np.median(floors, axis=0)
        ref_lum = float(ref @ lw)
        ref_tint = ref / ref_lum
        ref_sat = float((ref.max() - ref.min()) / max(ref.max(), 0.02))
    ref_med = float(np.median([i["med"] for i in items]))
    ref_gsat = float(np.median([i["sat"] for i in items]))
    for i in items:
        if i["floor"] is not None:
            # the floor is the same in every shot, so it is the yardstick: same brightness, same colour, same saturation
            lum = float(i["floor"] @ lw)
            gain = min(max(ref_lum / lum, 0.6), 1.6) * (1 + (np.clip(ref_tint / (i["floor"] / lum), 0.85, 1.18) - 1) * 0.8)
            moved = i["floor"] * gain
            now = float((moved.max() - moved.min()) / max(moved.max(), 0.02))
            sat = min(max(ref_sat / max(now, 0.02), 0.6), 1.25)
        else:
            # no floor in this shot: nudge it halfway towards the batch average of the whole picture
            gain = np.full(3, min(max((ref_med / i["med"]) ** 0.5, 0.8), 1.25))
            sat = min(max((ref_gsat / max(i["sat"], 0.02)) ** 0.5, 0.85, ), 1.15)
        i["gain"], i["satf"] = gain, sat
    # one shared lift for the whole batch so the photos stay consistent with each other
    lift = min(max(ED_PREP_WHITE / float(np.median([i["peak"] * i["gain"].max() for i in items])), 0.9), 2.2)
    plan = {}
    for i in items:
        gain = i["gain"] * lift
        over = gain.max() * i["peak"] / 0.97
        if over > 1:
            gain = gain / over
        plan[i["file"]] = {"window": i["window"], "gain": gain, "sat": i["satf"]}
    return plan

def ed_prep_colour(img, item):
    out = img.convert("RGB")
    table = []
    for c in range(3):
        table += [round(min(max(i / 255 * item["gain"][c], 0.0), 1.0) * 255) for i in range(256)]
    out = out.point(table)
    if abs(item["sat"] - 1) > 0.02:
        out = ImageEnhance.Color(out).enhance(item["sat"])
    return out

def ed_prep_crop(img, item):
    w, h = img.size
    if item["window"] is None:
        side = min(w, h)
        left, top = (w - side) // 2, (h - side) // 2
    else:
        cx, cy, side_w = item["window"]
        side = min(side_w * w, w, h)
        left = min(max(cx * w - side / 2, 0), w - side)
        top = min(max(cy * h - side / 2, 0), h - side)
    return img.crop((round(left), round(top), round(left) + round(side), round(top) + round(side)))

def ed_apply_plan(img, item):
    return ed_prep_colour(ed_prep_crop(img.convert("RGB"), item), item)

def ed_denoise(img, amount):
    r = max(0.5, amount * max(img.size) / 700)
    y, cb, cr = img.convert("YCbCr").split()
    cb = cb.filter(ImageFilter.GaussianBlur(r))
    cr = cr.filter(ImageFilter.GaussianBlur(r))
    y = Image.blend(y, y.filter(ImageFilter.GaussianBlur(r * 0.5)), min(1.0, amount * 0.6))
    return Image.merge("YCbCr", (y, cb, cr)).convert("RGB")

def ed_adjust(img, st):
    if not ed_look_active(st):
        return img
    w, h = img.size
    big = max(w, h)
    if st["noise"] > 0.001:
        img = ed_denoise(img, st["noise"])
    sharp, defin = st["sharpness"], st["definition"]
    fine = coarse = None
    if abs(sharp) > 0.001 or abs(defin) > 0.001:
        lum8 = img.convert("L")
        if abs(sharp) > 0.001:
            fine = np.asarray(lum8.filter(ImageFilter.GaussianBlur(max(0.6, big / 1100))))
        if abs(defin) > 0.001:
            coarse = np.asarray(lum8.filter(ImageFilter.GaussianBlur(max(3.0, big / 70))))
    src = np.asarray(img)
    out = np.empty((h, w, 3), np.uint8)
    xs = np.linspace(-1, 1, w, dtype=np.float32)
    ys = np.linspace(-1, 1, h, dtype=np.float32)
    colour = np.array(ED_HUES[int(st["hue"]) % len(ED_HUES)][1], np.float32)
    colour = colour / float(colour @ np.array([0.299, 0.587, 0.114], np.float32))
    step = max(64, 1_500_000 // w)
    for y0 in range(0, h, step):
        y1 = min(h, y0 + step)
        a = src[y0:y1].astype(np.float32) * (1 / 255)
        lum0 = ed_lum(a)
        if abs(st["exposure"]) > 0.001:
            a *= 2.0 ** (st["exposure"] * 1.5)
        bp = st["blackpoint"] * 0.15
        if abs(bp) > 0.0005:
            a = (a - bp) / (1.0 - bp)
        np.clip(a, 0, 1, out=a)
        hl, sh, br = st["highlights"], st["shadows"], st["brilliance"]
        if abs(hl) > 0.001 or abs(sh) > 0.001 or abs(br) > 0.001:
            lum = ed_lum(a)
            gain = 1 + hl * 0.45 * lum ** 2 + sh * 0.45 * (1 - lum) ** 2 + br * (0.3 * (1 - lum) ** 1.5 - 0.12 * lum ** 2)
            a *= gain[..., None]
        if st["fade"] > 0.001:
            a += (1 - a) * (st["fade"] * 0.16)
        if abs(st["contrast"]) > 0.001:
            a = (a - 0.5) * (1 + 0.8 * st["contrast"]) + 0.5
        if fine is not None:
            a += (sharp * 1.5) * (lum0 - fine[y0:y1] * (1 / 255))[..., None]
        if coarse is not None:
            a += (defin * 0.9) * (lum0 - coarse[y0:y1] * (1 / 255))[..., None]
        np.clip(a, 0, 1, out=a)
        sat, vib = st["saturation"], st["vibrancy"]
        if abs(sat) > 0.001 or abs(vib) > 0.001:
            lum = ed_lum(a)[..., None]
            s = 1.0 + sat
            if abs(vib) > 0.001:
                s = s + vib * ((1 - (a.max(axis=2) - a.min(axis=2))) ** 2)[..., None]
            a = lum + (a - lum) * s
        if abs(st["warmth"]) > 0.001:
            a[..., 0] *= 1 + 0.22 * st["warmth"]
            a[..., 2] *= 1 - 0.22 * st["warmth"]
        if abs(st["tint"]) > 0.001:
            a[..., 1] *= 1 - 0.14 * st["tint"]
            a[..., 0] *= 1 + 0.05 * st["tint"]
            a[..., 2] *= 1 + 0.05 * st["tint"]
        if st["hue_amount"] > 0.001:
            wash = np.clip(ed_lum(a)[..., None] * colour, 0, 1)
            a += (wash - a) * (0.45 * st["hue_amount"])
        vg = st["vignette"]
        if abs(vg) > 0.001:
            r2 = (ys[y0:y1, None] ** 2 + xs[None, :] ** 2) * 0.5
            m = np.clip((r2 - 0.25) / 0.75, 0, 1)
            m = (m * m * (3 - 2 * m))[..., None]
            if vg > 0:
                a *= 1 - 0.85 * vg * m
            else:
                a += (1 - a) * (-vg * 0.7) * m
        np.clip(a, 0, 1, out=a)
        out[y0:y1] = (a * 255 + 0.5).astype(np.uint8)
    res = Image.fromarray(out)
    if st["tilt"] > 0.001:
        blurred = res.filter(ImageFilter.GaussianBlur(max(1.0, st["tilt"] * big / 55)))
        centre = 0.5 + 0.35 * st["tilt_pos"]
        dist = np.abs(np.linspace(0, 1, h, dtype=np.float32) - centre)
        m = np.clip((dist - 0.12) / 0.28, 0, 1)
        m = m * m * (3 - 2 * m)
        mask = Image.fromarray((m * 255).astype(np.uint8).reshape(h, 1)).resize((w, h), Image.NEAREST)
        res = Image.composite(blurred, res, mask)
    return res

def ed_inscribed(w, h, angle):
    a = math.radians(abs(angle))
    s, c = abs(math.sin(a)), abs(math.cos(a))
    if s < 1e-9:
        return w, h
    long_side, short_side = (w, h) if w >= h else (h, w)
    if short_side <= 2 * s * c * long_side or abs(s - c) < 1e-10:
        x = 0.5 * short_side
        return (x / s, x / c) if w >= h else (x / c, x / s)
    cos2 = c * c - s * s
    return (w * c - h * s) / cos2, (h * c - w * s) / cos2

def ed_render(img, st, crop=True, adjust=True):
    out = img
    turns = st["turns"] % 4
    if turns:
        out = out.transpose({1: Image.Transpose.ROTATE_270, 2: Image.Transpose.ROTATE_180, 3: Image.Transpose.ROTATE_90}[turns])
    if st["flip_h"]:
        out = ImageOps.mirror(out)
    if st["flip_v"]:
        out = ImageOps.flip(out)
    angle = st["angle"]
    if abs(angle) >= 0.01:
        w, h = out.size
        rotated = out.rotate(angle, resample=Image.BICUBIC)
        cw, ch = ed_inscribed(w, h, angle)
        cw, ch = max(1, int(cw)), max(1, int(ch))
        x, y = (w - cw) // 2, (h - ch) // 2
        out = rotated.crop((x, y, x + cw, y + ch))
    if crop and st["crop"]:
        w, h = out.size
        l, t, r, b = st["crop"]
        box = (round(l * w), round(t * h), round(r * w), round(b * h))
        if box[2] - box[0] >= 1 and box[3] - box[1] >= 1:
            out = out.crop(box)
    if adjust:
        out = ed_adjust(out, st)
        if crop:
            out = ed_watermark(out, st)
    return out.copy() if out is img else out
def ed_crop_move(box, kind):
    l, t, r, b = box
    if kind == "cw":
        return [1 - b, l, 1 - t, r]
    if kind == "ccw":
        return [t, 1 - r, b, 1 - l]
    if kind == "flip_h":
        return [1 - r, t, 1 - l, b]
    return [l, 1 - b, r, 1 - t]

def ed_box_resize(box, hl, hr, ht, hb, x, y, dw, dh, ratio, mn=24):
    l, t, r, b = box
    x = min(max(x, 0), dw)
    y = min(max(y, 0), dh)
    if hl:
        l = min(x, r - mn)
    if hr:
        r = max(x, l + mn)
    if ht:
        t = min(y, b - mn)
    if hb:
        b = max(y, t + mn)
    if not ratio:
        return [l, t, r, b]
    dx = -1 if hl else 1 if hr else 0
    dy = -1 if ht else 1 if hb else 0
    ax = r if dx < 0 else l if dx > 0 else (l + r) / 2
    ay = b if dy < 0 else t if dy > 0 else (t + b) / 2
    w, h = r - l, b - t
    if dx and not dy:
        h = w / ratio
    elif dy and not dx:
        w = h * ratio
    else:
        w = max(w, h * ratio)
        h = w / ratio
    room_w = ax if dx < 0 else dw - ax if dx > 0 else 2 * min(ax, dw - ax)
    room_h = ay if dy < 0 else dh - ay if dy > 0 else 2 * min(ay, dh - ay)
    s = min(1.0, room_w / w, room_h / h)
    if s * min(w, h) < 4:
        return list(box)
    w, h = w * s, h * s
    l = ax - w if dx < 0 else ax if dx > 0 else ax - w / 2
    t = ay - h if dy < 0 else ay if dy > 0 else ay - h / 2
    return [l, t, l + w, t + h]

def ed_cursor(kind):
    if kind[0] == "move":
        return "fleur"
    if kind[0] == "new":
        return "crosshair"
    _, hl, hr, ht, hb = kind
    if (hl and ht) or (hr and hb):
        return "size_nw_se"
    if (hl and hb) or (hr and ht):
        return "size_ne_sw"
    return "size_we" if (hl or hr) else "size_ns"

def ed_exif(file):
    try:
        with Image.open(file) as im:
            exif = im.getexif()
            if not exif:
                return None
            try:
                exif.get_ifd(0x8769)
            except Exception:
                pass
            exif[274] = 1
            return exif.tobytes()
    except Exception:
        return None

def ed_small(img):
    probe = img.convert("RGB")
    probe.thumbnail((640, 640), Image.BILINEAR)
    found = ed_find_subject(probe)
    if found is not None:
        cx, cy, side, bg = found
        half = max(8, round(side / 2))
        probe = probe.crop((max(round(cx) - half, 0), max(round(cy) - half, 0), min(round(cx) + half, probe.width), min(round(cy) + half, probe.height)))
    else:
        w, h = probe.size
        probe = probe.crop((w // 8, h // 8, w - w // 8, h - h // 8))
    probe.thumbnail((256, 256))
    return probe

def ed_stats_small(small):
    a = np.asarray(small, np.float32) / 255
    lum = ed_lum(a)
    lo, hi = np.percentile(lum, [5, 95])
    return {
        "median": min(max(float(np.median(lum)), 0.03), 0.97),
        "spread": max(float(hi - lo), 0.05),
        "chroma": float((a.max(axis=2) - a.min(axis=2)).mean()),
        "rgb": [float(np.median(a[..., c])) for c in range(3)],
    }

def ed_stats(img):
    return ed_stats_small(ed_small(img))

def ed_normalise(img, t):
    small = ed_small(img)
    cur = ed_stats_small(small)
    gains = []
    for c in range(3):
        want = t["rgb"][c] / t["median"]
        have = max(cur["rgb"][c], 0.01) / cur["median"]
        gains.append(min(max(want / have, 0.85), 1.18))
    mean_gain = sum(gains) / 3
    gains = [g / mean_gain for g in gains]
    balance = []
    for g in gains:
        balance += [round(min(i * g, 255)) for i in range(256)]
    img = img.point(balance)
    small = small.point(balance)
    cur = ed_stats_small(small)
    g = min(max(math.log(t["median"]) / math.log(cur["median"]), 0.7), 1.5)
    gam = [(i / 255) ** g for i in range(256)]
    first = small.point([round(255 * v) for v in gam] * 3)
    spread = min(max(t["spread"] / ed_stats_small(first)["spread"], 0.8), 1.25)
    mid = t["median"]
    lut = [round(min(max((gam[i] - mid) * spread + mid, 0.0), 1.0) * 255) for i in range(256)]
    chroma = ed_stats_small(small.point(lut * 3))["chroma"]
    sat = min(max(t["chroma"] / max(chroma, 0.01), 0.6), 1.3)
    out = img.point(lut * 3)
    if abs(sat - 1) > 0.02:
        out = ImageEnhance.Color(out).enhance(sat)
    return out

def ed_autobox(img):
    small = img.copy()
    small.thumbnail((256, 256))
    a = np.asarray(small.convert("RGB"), np.float32)
    h, w = a.shape[:2]
    edge = np.concatenate([a[:5].reshape(-1, 3), a[-5:].reshape(-1, 3), a[:, :5].reshape(-1, 3), a[:, -5:].reshape(-1, 3)])
    mask = np.abs(a - np.median(edge, axis=0)).sum(axis=2) > 70
    ys, xs = np.nonzero(mask)
    if len(xs) < 0.02 * w * h:
        return None
    l, r = np.percentile(xs, [0.5, 99.5])
    t, b = np.percentile(ys, [0.5, 99.5])
    half = min(max(r - l, b - t) / 2 * 1.05, w / 2, h / 2)
    cx = min(max((l + r) / 2, half), w - half)
    cy = min(max((t + b) / 2, half), h - half)
    return [(cx - half) / w, (cy - half) / h, (cx + half) / w, (cy + half) / h]

def ed_otsu(values, bins=64):
    hist, edges = np.histogram(values, bins=bins)
    hist = hist.astype(np.float64)
    mids = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(hist)
    w1 = hist.sum() - w0
    m0 = np.cumsum(hist * mids)
    with np.errstate(divide="ignore", invalid="ignore"):
        between = w0 * w1 * (m0 / w0 - (m0[-1] - m0) / w1) ** 2
    return float(mids[int(np.argmax(np.nan_to_num(between)))])

def ed_find_subject(img):
    small = img.convert("RGB")
    small.thumbnail((256, 256))
    small = small.filter(ImageFilter.GaussianBlur(5))
    a = np.asarray(small, np.float32)
    h, w = a.shape[:2]
    edge = np.concatenate([a[:6].reshape(-1, 3), a[-6:].reshape(-1, 3), a[:, :6].reshape(-1, 3), a[:, -6:].reshape(-1, 3)])
    bg = np.median(edge, axis=0)
    dist = np.abs(a - bg).sum(axis=2)
    mask = dist > max(ed_otsu(dist.ravel()), 25.0)
    cleaned = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(9))
    mask = np.asarray(cleaned) > 127
    ys, xs = np.nonzero(mask)
    area = len(xs) / (w * h)
    if area < 0.03 or area > 0.85:
        return None
    l, r = np.percentile(xs, [1, 99])
    t, b = np.percentile(ys, [1, 99])
    s = img.width / w
    return ((l + r + 1) / 2 * s, (t + b + 1) / 2 * s, max(r - l, b - t) * s, tuple(int(v) for v in bg))

def ed_centre(img, margin=1.1):
    found = ed_find_subject(img)
    if found is None:
        logging.warning("Centre: could not find the subject, left as is.")
        return img
    cx, cy, side, bg = found
    half = max(8, round(side * margin / 2))
    half = min(half, img.width // 2, img.height // 2)
    x0 = min(max(round(cx) - half, 0), img.width - half * 2)
    y0 = min(max(round(cy) - half, 0), img.height - half * 2)
    return img.convert("RGB").crop((x0, y0, x0 + half * 2, y0 + half * 2))

def ed_geometry(img, st, centre):
    out = ed_render(img, st, adjust=False)
    if centre:
        out = ed_centre(out)
    return out

def ed_autofix(img, white=0.92, strength=0.8):
    small = img.convert("RGB")
    small.thumbnail((256, 256))
    a = np.asarray(small, np.float32) / 255
    hi = np.array([max(float(np.percentile(a[..., c], 99.5)), 0.05) for c in range(3)])
    lo = np.array([float(np.percentile(a[..., c], 0.5)) for c in range(3)])
    balance = np.clip(hi.mean() / hi, 0.8, 1.25)
    balance = 1 + (balance - 1) * strength
    top = float(ed_lum(np.array([[hi * balance]]))[0, 0])
    gain = min(max(white / max(top, 0.1), 0.8), 3.0)
    black = min(float(lo.mean()) * 0.8, 0.1)
    table = []
    for c in range(3):
        for i in range(256):
            value = (i / 255 * balance[c] - black) * gain
            table.append(round(min(max(value, 0.0), 1.0) * 255))
    return img.convert("RGB").point(table)

def ed_export(file, st, target=None, centre=False, item=None):
    try:
        big = 1 << 14
        img = load_image(file, (big, big), need=big)
        own_geometry = bool(st["crop"]) or st["turns"] % 4 != 0 or st["flip_h"] or st["flip_v"] or abs(st["angle"]) >= 0.01
        if item is not None and not own_geometry:
            img = ed_apply_plan(img, item)
        else:
            img = ed_geometry(img, st, centre)
            if item is not None:
                img = ed_prep_colour(img, item)
        if item is None and st.get("auto"):
            img = ed_autofix(img)
        elif target is not None:
            img = ed_normalise(img, target)
        img = ed_adjust(img, st)
        img = ed_watermark(img, st)
        folder = file.parent / ED_FOLDER
        folder.mkdir(exist_ok=True)
        ext = file.suffix.lower()
        if ext not in ED_SAVE_FORMATS:
            ext = ".jpg"
        dest = folder / f"{file.stem}_edit{ext}"
        n = 1
        while dest.exists():
            dest = folder / f"{file.stem}_edit_{n}{ext}"
            n += 1
        fmt = ED_SAVE_FORMATS[ext]
        opts = {}
        if fmt in ("JPEG", "WEBP"):
            opts["quality"] = 95
        if fmt == "JPEG":
            opts["optimize"] = True
        if fmt in ("JPEG", "WEBP", "PNG"):
            exif = ed_exif(file)
            if exif:
                opts["exif"] = exif
        tmp = dest.with_name(dest.name + ".tmp")
        try:
            img.save(tmp, format=fmt, **opts)
            os.replace(tmp, dest)
        except Exception:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise
        logging.info("Saved edited photo %s", dest)
        return f"✓ Saved {dest.name}."
    except Exception:
        logging.exception("Could not save the edited photo %s.", file.name)
        return "✗ Could not save the photo (see log)."

pics_view = "grid"
focus_mode = False

class Editor:
    def __init__(self, parent):
        self.file = None
        self.token = 0
        self.st = ed_copy(ED_DEFAULT)
        self.saved = ed_copy(self.st)
        self.undo = []
        self.redo = []
        self.trial = None
        self.skip_release = False
        self.crop_mode = False
        self.need_fit = False
        self.box = None
        self.drag = None
        self.src = None
        self.photo = None
        self.disp = (0, 0, 1, 1)
        self.job = None
        self.sliders = {}
        self.small = None
        self.stage = None
        self.stage_key = None
        self.swatches = []
        self.batch = []
        self.batch_idx = 0
        self.cache = {}
        self.click_at = None
        self.build(parent)

    def dirty(self):
        return self.file is not None and self.st != self.saved

    def build(self, parent):
        s = ui_scale()
        self.cw, self.ch = round(610 * s), round(436 * s)
        self.bg = ed_background(self.cw, self.ch)
        frame = ctk.CTkFrame(parent, fg_color="#14151c", corner_radius=0)
        self.frame = frame
        self.win = frame
        self.cv = tk.Canvas(frame, width=self.cw, height=self.ch, bg="#14151c", highlightthickness=0, bd=0)
        self.cv.grid(row=0, column=0, padx=(12, 6), pady=(6, 2))
        self.info = tk.Label(frame, text="", bg="#14151c", fg="#8f95a8", font=(UI_FONT, 12))
        self.info.grid(row=1, column=0, pady=(0, 6))
        panel = ctk.CTkFrame(frame, fg_color="#1b1d27", corner_radius=0)
        panel.grid(row=0, column=1, rowspan=2, sticky="ns")
        panel.grid_columnconfigure(0, minsize=254)
        font = (UI_FONT, 13)

        def make_button(master, text, command, width, **extra):
            return ctk.CTkButton(master, text=text, command=command, font=font, width=width, height=24, **extra)

        actions = ctk.CTkFrame(panel, fg_color="transparent")
        actions.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")
        ctk.CTkButton(actions, text="Save a copy", command=self.save, font=(UI_FONT, 15), width=118, height=30, fg_color="#2e8b57", hover_color="#37a367").grid(row=0, column=0, padx=(0, 6))
        ctk.CTkButton(actions, text="Bulk edit...", command=lambda: bulk_open(bulk_files()), font=(UI_FONT, 15), width=112, height=30).grid(row=0, column=1)
        top = ctk.CTkFrame(panel, fg_color="transparent")
        top.grid(row=1, column=0, padx=10, pady=(8, 0), sticky="w")
        self.undo_button = make_button(top, "Undo", self.do_undo, 68)
        self.redo_button = make_button(top, "Redo", self.do_redo, 68)
        self.reset_button = make_button(top, "Reset look", self.reset_look, 88)
        self.undo_button.grid(row=0, column=0, padx=(0, 5))
        self.redo_button.grid(row=0, column=1, padx=(0, 5))
        self.reset_button.grid(row=0, column=2)
        presets = ctk.CTkFrame(panel, fg_color="transparent")
        presets.grid(row=2, column=0, padx=10, pady=(8, 0), sticky="w")
        self.preset_menu = ctk.CTkOptionMenu(presets, values=self.preset_labels(), command=self.preset_pick, font=font, width=134, height=24, dynamic_resizing=False)
        self.preset_menu.set(ED_PRESET_HINT)
        self.preset_menu.grid(row=0, column=0, padx=(0, 5))
        make_button(presets, "Save", self.preset_save, 50).grid(row=0, column=1, padx=(0, 5))
        make_button(presets, "Del", self.preset_delete, 40, fg_color="#8b2e2e", hover_color="#a33b3b").grid(row=0, column=2)
        body = ctk.CTkScrollableFrame(panel, width=222, height=300, fg_color="transparent", scrollbar_button_color="#2c3043", scrollbar_button_hover_color="#3a4060")
        body.grid(row=3, column=0, padx=(6, 2), pady=(6, 10), sticky="n")

        def heading(text, row):
            ctk.CTkLabel(body, text=text.upper(), font=(UI_FONT, 13), text_color="#4da3ff").grid(row=row, column=0, padx=6, pady=(14, 0), sticky="w")

        row = 0
        heading("Geometry", row)
        row += 1
        rot = ctk.CTkFrame(body, fg_color="transparent")
        rot.grid(row=row, column=0, padx=2, pady=(6, 0), sticky="w")
        row += 1
        for col, (text, command) in enumerate((("Left", lambda: self.rotate(-1)), ("Right", lambda: self.rotate(1)), ("Flip H", lambda: self.flip("flip_h")), ("Flip V", lambda: self.flip("flip_v")))):
            make_button(rot, text, command, 48).grid(row=0, column=col, padx=(0, 4))
        crop_row = ctk.CTkFrame(body, fg_color="transparent")
        crop_row.grid(row=row, column=0, padx=2, pady=(6, 0), sticky="w")
        row += 1
        self.crop_button = make_button(crop_row, "Crop", self.crop_start, 60)
        self.crop_button.grid(row=0, column=0, padx=(0, 5))
        self.ratio_menu = ctk.CTkOptionMenu(crop_row, values=list(ED_RATIOS), command=self.ratio_changed, font=font, width=126, height=24, dynamic_resizing=False)
        self.ratio_menu.set("Free")
        self.ratio_menu.grid(row=0, column=1)
        self.crop_actions = ctk.CTkFrame(body, fg_color="transparent")
        self.crop_actions_row = row
        row += 1
        make_button(self.crop_actions, "Apply", lambda: self.crop_end(True), 60, fg_color="#2e8b57").grid(row=0, column=0, padx=(0, 5))
        make_button(self.crop_actions, "Cancel", lambda: self.crop_end(False), 60).grid(row=0, column=1, padx=(0, 5))
        make_button(self.crop_actions, "Whole", self.crop_whole, 60).grid(row=0, column=2)
        self.add_slider(body, row, "angle", "Straighten", -15.0, 15.0)
        row += 2
        for title, items in ED_GROUPS:
            heading(title, row)
            row += 1
            for key, text, lo, hi in items:
                if key == "hue_amount":
                    swatch_row = ctk.CTkFrame(body, fg_color="transparent")
                    swatch_row.grid(row=row, column=0, padx=6, pady=(8, 0), sticky="w")
                    row += 1
                    for i, (name, rgb) in enumerate(ED_HUES):
                        colour = "#%02x%02x%02x" % tuple(int(c * 255) for c in rgb)
                        button = ctk.CTkButton(swatch_row, text="", width=20, height=20, corner_radius=10, fg_color=colour, hover_color=colour, border_width=0, border_color="#ffffff", command=lambda i=i: self.commit("hue", i))
                        button.grid(row=0, column=i, padx=(0, 4))
                        self.swatches.append(button)
                self.add_slider(body, row, key, text, lo, hi)
                row += 2
        heading("Watermark", row)
        row += 1
        self.wm_check = ctk.CTkCheckBox(body, text="Add watermark", command=self.wm_toggle, font=(UI_FONT, 14))
        self.wm_check.grid(row=row, column=0, padx=6, pady=(6, 0), sticky="w")
        row += 1
        wm_row = ctk.CTkFrame(body, fg_color="transparent")
        wm_row.grid(row=row, column=0, padx=2, pady=(6, 0), sticky="w")
        row += 1
        self.wm_corner_menu = ctk.CTkOptionMenu(wm_row, values=WM_CORNERS, command=lambda c: self.commit("wm_corner", c), font=font, width=110, height=24, dynamic_resizing=False)
        self.wm_corner_menu.grid(row=0, column=0, padx=(0, 5))
        make_button(wm_row, "Choose image", self.wm_choose, 100).grid(row=0, column=1)
        self.add_slider(body, row, "wm_size", "Size (% of width)", 1.0, 60.0)
        row += 2
        self.cv.bind("<ButtonPress-1>", self.cv_press)
        self.cv.bind("<B1-Motion>", self.cv_drag)
        self.batch_button = ctk.CTkButton(actions, text="Apply look to all", command=lambda: bulk_open(self.batch), font=(UI_FONT, 15), width=236, height=30, fg_color="#1f6aa5")
        self.cv.bind("<ButtonRelease-1>", self.cv_release)
        self.cv.bind("<Motion>", self.cv_motion)
        self.sync()

    def add_slider(self, master, row, key, text, lo, hi):
        head = ctk.CTkFrame(master, fg_color="transparent")
        head.grid(row=row, column=0, padx=6, pady=(8, 0), sticky="ew")
        head.grid_columnconfigure(0, weight=1)
        label = ctk.CTkLabel(head, text=text, font=(UI_FONT, 14), anchor="w")
        label.grid(row=0, column=0, sticky="w")
        reset = ctk.CTkButton(head, text="↺", width=22, height=20, font=(UI_FONT, 13), fg_color="#2c3043", hover_color="#3a4060", command=lambda k=key: self.reset_one(k))
        reset.grid(row=0, column=1, sticky="e")
        slider = ctk.CTkSlider(master, from_=lo, to=hi, width=196, command=lambda v, k=key: self.slide(k, v))
        slider.set(ED_DEFAULT[key])
        slider.grid(row=row + 1, column=0, padx=6, sticky="w")
        slider.bind("<ButtonRelease-1>", lambda e, k=key: self.slide_done(k))
        slider.bind("<Double-Button-1>", lambda e, k=key: self.slide_reset(k))
        self.sliders[key] = (slider, label, text, lo, reset)
    def wm_toggle(self):
        want = bool(self.wm_check.get())
        if want and not wm_ready():
            if not watermark_pick():
                self.wm_check.deselect()
                return
        self.commit("wm_on", want)

    def wm_choose(self):
        if watermark_pick() and self.st["wm_on"]:
            self.refresh()
    def reset_one(self, key):
        self.trial = None
        self.commit(key, ED_DEFAULT[key])

    def rescale(self):
        s = ui_scale()
        self.cache.clear()
        self.cw, self.ch = round(610 * s), round(436 * s)
        self.bg = ed_background(self.cw, self.ch)
        self.cv.configure(width=self.cw, height=self.ch)
        self.stage_key = None
        self.refresh()

    def load_preview(self, file):
        side = int(max(self.cw, self.ch) * 1.5)
        img = load_image(file, (side * 2, side * 2), need=side)
        img.thumbnail((side, side), Image.BILINEAR)
        small = img.copy()
        s2 = round(max(self.cw, self.ch) * 1.05)
        small.thumbnail((s2, s2), Image.BILINEAR)
        return img, small

    def cache_put(self, file, pair):
        self.cache[file] = pair
        while len(self.cache) > 12:
            try:
                self.cache.pop(next(iter(self.cache)))
            except (StopIteration, KeyError, RuntimeError):
                break

    def prefetch(self, file):
        if file in self.cache:
            return

        def work():
            try:
                self.cache_put(file, self.load_preview(file))
            except Exception:
                logging.exception("Could not prefetch %s.", file.name)

        threading.Thread(target=work, daemon=True).start()

    def open_file(self, file, keep_look=False):
        self.file = file
        self.token += 1
        token = self.token
        if not keep_look:
            self.st = ed_copy(ED_DEFAULT)
            self.saved = ed_copy(self.st)
            self.undo = []
            self.redo = []
            self.preset_menu.set(ED_PRESET_HINT)
        self.trial = None
        self.stage_key = None
        self.crop_mode = False
        self.drag = None
        self.box = None
        self.crop_actions.grid_forget()
        self.crop_button.configure(state="normal")
        self.cv.configure(cursor="")
        hit = self.cache.get(file)
        if hit is not None:
            self.src, self.small = hit
            self.sync()
            return
        self.src = None
        self.small = None
        if not keep_look:
            self.cv.delete("all")
        self.sync()
        self.info.configure(text="Loading...")
        holder = {}

        def work():
            try:
                holder["img"] = self.load_preview(file)
            except Exception:
                logging.exception("Could not open %s for editing.", file.name)
                holder["img"] = False

        def poll():
            if token != self.token:
                return
            try:
                if "img" not in holder:
                    self.frame.after(60, poll)
                    return
                if holder["img"] is False:
                    messagebox.showwarning("Specorde", "Could not open this photo for editing.")
                    editor_back(True)
                    return
                self.src, self.small = holder["img"]
                self.cache_put(file, holder["img"])
                self.refresh()
            except Exception:
                logging.exception("Editor loading check failed.")

        threading.Thread(target=work, daemon=True).start()
        self.frame.after(60, poll)

    def batch_start(self, files):
        self.batch = list(files)
        self.batch_idx = 0
        self.open_file(self.batch[0])
        self.batch_update()
        for k in (1, 2):
            self.prefetch(self.batch[k % len(self.batch)])

    def batch_step(self, delta):
        if len(self.batch) < 2:
            return
        if self.crop_mode:
            self.crop_end(True)
        n = len(self.batch)
        self.batch_idx = (self.batch_idx + delta) % n
        self.open_file(self.batch[self.batch_idx], keep_look=True)
        self.batch_update()
        for k in (1, 2):
            self.prefetch(self.batch[(self.batch_idx + k) % n])

    def batch_update(self):
        n = len(self.batch)
        if n > 1:
            self.batch_button.configure(text=f"Apply look to all {n} photos")
            self.batch_button.grid(row=1, column=0, columnspan=2, pady=(6, 0), sticky="w")
            ed_name_label.configure(text=f"{trim(self.file.name, 40)}  ({self.batch_idx + 1}/{n})")
        else:
            self.batch_button.grid_forget()

    # ---- presets
    def preset_labels(self):
        return [ED_PRESET_HINT] + list(ED_BUILTIN) + ["★ " + name for name in ed_presets]

    def preset_refresh(self, selected):
        self.preset_menu.configure(values=self.preset_labels())
        self.preset_menu.set(selected)

    def preset_pick(self, label):
        if label == ED_PRESET_HINT:
            return
        if label in ED_BUILTIN:
            look = ED_BUILTIN[label]
        else:
            look = ed_presets.get(label[2:] if label.startswith("★ ") else label)
        if look is None:
            return
        if self.crop_mode:
            self.crop_end(False)
        self.push()
        for key in ED_LOOK:
            self.st[key] = 0.0
        self.st["hue"] = int(look.get("hue", 0))
        for key, value in look.items():
            if key in ED_LOOK:
                self.st[key] = float(value)
        self.sync()

    def preset_save(self):
        look = {k: round(self.st[k], 3) for k in ED_LOOK if abs(self.st[k]) > 0.001}
        if not look:
            messagebox.showinfo("Specorde", "Nothing to save yet. Move some sliders first.")
            return
        look["hue"] = int(self.st["hue"])
        name = (ctk.CTkInputDialog(text="Name for this look (max 24 characters):", title="Save look").get_input() or "").strip()[:24]
        if not name:
            return
        if name in ED_BUILTIN:
            messagebox.showwarning("Specorde", "That name belongs to a built-in look. Pick another one.")
            return
        ed_presets[name] = look
        ed_presets_save()
        self.preset_refresh("★ " + name)

    def preset_delete(self):
        label = self.preset_menu.get()
        if not label.startswith("★ "):
            messagebox.showinfo("Specorde", "Pick one of your own looks (marked with a star) to delete it.")
            return
        name = label[2:]
        if name in ed_presets and messagebox.askyesno("Specorde", f"Delete the look '{name}'?"):
            del ed_presets[name]
            ed_presets_save()
            self.preset_refresh(ED_PRESET_HINT)

    def reset_look(self):
        if self.crop_mode:
            self.crop_end(False)
        if ed_look_active(self.st):
            self.push()
            for key in ED_LOOK:
                self.st[key] = 0.0
            self.sync()
        self.preset_menu.set(ED_PRESET_HINT)

    # ---- state
    def push(self):
        self.undo.append(ed_copy(self.st))
        del self.undo[:-100]
        self.redo.clear()

    def sync(self):
        if self.st["wm_on"]:
            self.wm_check.select()
        else:
            self.wm_check.deselect()
        self.wm_corner_menu.set(self.st["wm_corner"])
        for key, (slider, label, text, lo, reset) in self.sliders.items():
            slider.set(self.st[key])
            self.value_label(key, self.st[key])
            reset.configure(state="normal" if abs(self.st[key] - ED_DEFAULT[key]) > 0.001 else "disabled")
        for i, button in enumerate(self.swatches):
            button.configure(border_width=2 if i == int(self.st["hue"]) else 0)
        self.undo_button.configure(state="normal" if self.undo else "disabled")
        self.redo_button.configure(state="normal" if self.redo else "disabled")
        self.reset_button.configure(state="normal" if ed_look_active(self.st) else "disabled")
        self.refresh()

    def value_label(self, key, value):
        slider, label, text, lo, reset = self.sliders[key]
        if key == "angle":
            shown = f"{value:+.1f}°"
        elif key == "wm_size":
            shown = f"{value:.0f}%"
        elif lo < 0:
            shown = f"{round(value * 100):+d}"
        else:
            shown = f"{round(value * 100)}"
        label.configure(text=f"{text}   {shown}")

    def commit(self, key, value):
        if self.st[key] != value:
            self.push()
            self.st[key] = value
        self.sync()

    def do_undo(self):
        if self.crop_mode:
            self.crop_end(False)
        if self.undo:
            self.redo.append(ed_copy(self.st))
            self.st = self.undo.pop()
            self.sync()

    def do_redo(self):
        if self.crop_mode:
            self.crop_end(False)
        if self.redo:
            self.undo.append(ed_copy(self.st))
            self.st = self.redo.pop()
            self.sync()

    # ---- sliders
    def slide(self, key, value):
        value = round(float(value), 2)
        self.trial = ed_copy(self.st)
        self.trial[key] = value
        self.value_label(key, value)
        if self.job is None:
            self.job = self.win.after(30, self.refresh)

    def slide_done(self, key):
        if self.skip_release:
            self.skip_release = False
            self.trial = None
            self.refresh()
            return
        if self.trial is None:
            return
        value = self.trial[key]
        self.trial = None
        self.commit(key, value)

    def slide_reset(self, key):
        self.skip_release = True
        self.trial = None
        self.commit(key, ED_DEFAULT[key])

    # ---- rotate / flip
    def rotate(self, d):
        self.crop_end(True)
        st = self.st
        self.push()
        mirrored = st["flip_h"] != st["flip_v"]
        st["turns"] = (st["turns"] + (-d if mirrored else d)) % 4
        if st["crop"]:
            st["crop"] = ed_crop_move(st["crop"], "cw" if d > 0 else "ccw")
        self.sync()

    def flip(self, key):
        self.crop_end(True)
        st = self.st
        self.push()
        st[key] = not st[key]
        st["angle"] = -st["angle"]
        if st["crop"]:
            st["crop"] = ed_crop_move(st["crop"], key)
        self.sync()

    # ---- drawing
    def refresh(self):
        self.job = None
        if self.src is None:
            return
        st = self.trial or self.st
        fast = self.trial is not None and self.small is not None
        base = self.small if fast else self.src
        try:
            img = ed_render(base, st, crop=not self.crop_mode)
        except Exception:
            logging.exception("Could not draw the preview.")
            return
        iw, ih = img.size
        scale = min((self.cw - 28) / iw, (self.ch - 28) / ih)
        dw, dh = max(1, round(iw * scale)), max(1, round(ih * scale))
        ox, oy = (self.cw - dw) // 2, (self.ch - dh) // 2
        self.disp = (ox, oy, dw, dh)
        key = (self.cw, self.ch, ox, oy, dw, dh)
        if key != self.stage_key:
            stage = self.bg.copy()
            shadow = Image.new("L", stage.size, 0)
            ImageDraw.Draw(shadow).rectangle((ox + 2, oy + 8, ox + dw + 2, oy + dh + 8), fill=170)
            shadow = shadow.filter(ImageFilter.GaussianBlur(10))
            stage.paste((0, 0, 0), (0, 0) + stage.size, shadow)
            ImageDraw.Draw(stage).rectangle((ox - 1, oy - 1, ox + dw, oy + dh), outline="#2f3347")
            self.stage = stage
            self.stage_key = key
        view = self.stage.copy()
        view.paste(img.resize((dw, dh), Image.BILINEAR), (ox, oy))
        self.photo = ImageTk.PhotoImage(view)
        self.cv.delete("all")
        self.cv.create_image(0, 0, image=self.photo, anchor="nw")
        if self.crop_mode:
            if self.need_fit:
                self.need_fit = False
                self.box_fit()
            self.draw_box()
            text = "Drag the corners, edges or the inside · Enter applies · Esc cancels"
        elif len(self.batch) > 1:
            text = f"Photo {self.batch_idx + 1}/{len(self.batch)} · click or Space: next · right-click: back · Ctrl+S saves this one"
        else:
            text = "C crop · Ctrl+Z undo · Ctrl+Y redo · Ctrl+S save · Esc back · double-click a slider to reset it"
        self.info.configure(text=text)

    def draw_box(self):
        ox, oy, dw, dh = self.disp
        l, t, r, b = self.box
        x1, y1, x2, y2 = ox + l * dw, oy + t * dh, ox + r * dw, oy + b * dh
        for rect in ((ox, oy, ox + dw, y1), (ox, y2, ox + dw, oy + dh), (ox, y1, x1, y2), (x2, y1, ox + dw, y2)):
            self.cv.create_rectangle(*rect, fill="#000000", stipple="gray50", outline="", tags="box")
        for k in (1, 2):
            self.cv.create_line(x1 + (x2 - x1) * k / 3, y1, x1 + (x2 - x1) * k / 3, y2, fill="#8a8f9c", tags="box")
            self.cv.create_line(x1, y1 + (y2 - y1) * k / 3, x2, y1 + (y2 - y1) * k / 3, fill="#8a8f9c", tags="box")
        self.cv.create_rectangle(x1, y1, x2, y2, outline="#ffd24a", width=2, tags="box")
        for hx in (x1, (x1 + x2) / 2, x2):
            for hy in (y1, (y1 + y2) / 2, y2):
                if (hx, hy) != ((x1 + x2) / 2, (y1 + y2) / 2):
                    self.cv.create_rectangle(hx - 4, hy - 4, hx + 4, hy + 4, fill="#ffd24a", outline="#101117", tags="box")

    # ---- crop
    def ratio_value(self):
        ratio = ED_RATIOS.get(self.ratio_menu.get())
        if ratio == "orig":
            return self.disp[2] / self.disp[3]
        return ratio

    def ratio_changed(self, choice=None):
        if self.crop_mode:
            self.need_fit = True
            self.refresh()

    def box_fit(self):
        ratio = self.ratio_value()
        if not ratio:
            return
        dw, dh = self.disp[2], self.disp[3]
        l, t, r, b = self.box
        bw, bh = (r - l) * dw, (b - t) * dh
        if bw / bh > ratio:
            nw, nh = bh * ratio, bh
        else:
            nw, nh = bw, bw / ratio
        cx, cy = (l + r) / 2, (t + b) / 2
        self.box = [cx - nw / dw / 2, cy - nh / dh / 2, cx + nw / dw / 2, cy + nh / dh / 2]

    def crop_start(self):
        if self.src is None or self.crop_mode:
            return
        self.crop_mode = True
        self.need_fit = True
        self.box = list(self.st["crop"]) if self.st["crop"] else [0.0, 0.0, 1.0, 1.0]
        self.crop_actions.grid(row=self.crop_actions_row, column=0, padx=2, pady=(6, 0), sticky="w")
        self.crop_button.configure(state="disabled")
        self.refresh()

    def crop_whole(self):
        if self.crop_mode:
            self.box = [0.0, 0.0, 1.0, 1.0]
            self.need_fit = True
            self.refresh()

    def crop_end(self, apply):
        if not self.crop_mode:
            return
        if apply:
            new = [round(v, 5) for v in self.box]
            if new[2] - new[0] > 0.999 and new[3] - new[1] > 0.999:
                new = None
            if new != self.st["crop"]:
                self.push()
                self.st["crop"] = new
        self.crop_mode = False
        self.drag = None
        self.cv.configure(cursor="")
        self.crop_actions.grid_forget()
        self.crop_button.configure(state="normal")
        self.sync()

    def rel(self, e):
        return e.x - self.disp[0], e.y - self.disp[1]

    def hit(self, x, y):
        dw, dh = self.disp[2], self.disp[3]
        l, t, r, b = self.box[0] * dw, self.box[1] * dh, self.box[2] * dw, self.box[3] * dh
        m = 12
        in_x = l - m <= x <= r + m
        in_y = t - m <= y <= b + m
        hl = abs(x - l) <= m and in_y
        hr = abs(x - r) <= m and in_y and not hl
        ht = abs(y - t) <= m and in_x
        hb = abs(y - b) <= m and in_x and not ht
        if hl or hr or ht or hb:
            return ("size", hl, hr, ht, hb)
        if l <= x <= r and t <= y <= b:
            return ("move",)
        return ("new",)

    def cv_motion(self, e):
        if not self.crop_mode or self.box is None or self.drag is not None:
            return
        x, y = self.rel(e)
        self.cv.configure(cursor=ed_cursor(self.hit(x, y)))

    def cv_press(self, e):
        canvas.focus_set()
        self.click_at = (e.x, e.y)
        if not self.crop_mode or self.box is None:
            return
        dw, dh = self.disp[2], self.disp[3]
        x, y = self.rel(e)
        kind = self.hit(x, y)
        box = [self.box[0] * dw, self.box[1] * dh, self.box[2] * dw, self.box[3] * dh]
        if kind[0] == "new":
            x, y = min(max(x, 0), dw), min(max(y, 0), dh)
            box = [x, y, x, y]
        self.drag = {"kind": kind, "x": x, "y": y, "box": box}

    def cv_release(self, e):
        self.drag = None
        start, self.click_at = self.click_at, None
        if len(self.batch) > 1 and not self.crop_mode and start and math.hypot(e.x - start[0], e.y - start[1]) < 5:
            self.batch_step(1)

    def cv_drag(self, e):
        d = self.drag
        if d is None:
            return
        dw, dh = self.disp[2], self.disp[3]
        x, y = self.rel(e)
        l, t, r, b = d["box"]
        if d["kind"][0] == "move":
            w, h = r - l, b - t
            nl = min(max(l + x - d["x"], 0), dw - w)
            nt = min(max(t + y - d["y"], 0), dh - h)
            new = [nl, nt, nl + w, nt + h]
        else:
            if d["kind"][0] == "new":
                hl, ht = x < d["x"], y < d["y"]
                flags = (hl, not hl, ht, not ht)
            else:
                flags = d["kind"][1:]
            new = ed_box_resize(d["box"], *flags, x, y, dw, dh, self.ratio_value())
        self.box = [new[0] / dw, new[1] / dh, new[2] / dw, new[3] / dh]
        self.cv.delete("box")
        self.draw_box()

    # ---- save
    def save(self):
        if self.src is None or self.file is None:
            return
        self.crop_end(True)
        file = self.file
        st = ed_copy(self.st)
        holder = {}
        self.info.configure(text="Saving a copy...")
        q.put(("status", "Saving photo..."))

        def work():
            holder["line"] = ed_export(file, st)

        def poll():
            global pics_stamp
            if "line" not in holder:
                canvas.after(150, poll)
                return
            ok = holder["line"].startswith("✓")
            q.put(("summary_clear", None))
            q.put(("summary_add", holder["line"]))
            q.put(("summary_hide_later", None))
            q.put(("status", "Photo saved!" if ok else "Saving failed. See log..."))
            q.put(("status_reset", None))
            if "target_folder" in globals() and file.parent == target_folder:
                pics_stamp = folder_stamp()
            if self.file == file:
                if ok:
                    self.saved = ed_copy(st)
                self.info.configure(text=holder["line"])

        threading.Thread(target=work, daemon=True).start()
        canvas.after(150, poll)

def ed_focus(on):
    global focus_mode
    if on == focus_mode:
        return
    focus_mode = on
    if on:
        left.grid_remove()
        middle.configure(width=892)
    else:
        middle.configure(width=678)
        left.grid()

def editing():
    return currently_open == 3 and pics_view == "edit" and ed_view.file is not None

def editor_back(force=False):
    global pics_view
    if ed_view.crop_mode:
        ed_view.crop_end(False)
    if not force and ed_view.dirty():
        if not messagebox.askyesno("Specorde", "Go back without saving your changes?"):
            return
    ed_view.file = None
    ed_view.batch = []
    ed_view.src = None
    ed_view.token += 1
    pics_view = "grid"
    pictures_open()

def editor_open_batch(files):
    global pics_view
    files = [Path(f) for f in files if Path(f).suffix.lower() in pic_suffixes]
    if not files:
        messagebox.showinfo("Specorde", "No photos to edit.")
        return
    if ed_view.file is not None and ed_view.dirty():
        if not messagebox.askyesno("Specorde", "Open these photos without saving your changes?"):
            return
    inspect_close_all()
    compare_close()
    peek_close()
    ed_view.batch_start(files)
    pics_view = "edit"
    pictures_open()
    canvas.focus_set()

def editor_open(file):
    global pics_view
    file = Path(file)
    if file.suffix.lower() not in pic_suffixes:
        messagebox.showwarning("Specorde", "This file type can't be edited.")
        return
    if ed_view.file is not None and ed_view.file != file and ed_view.dirty():
        if not messagebox.askyesno("Specorde", "Open another photo without saving your changes?"):
            return
    inspect_close_all()
    compare_close()
    peek_close()
    ed_view.batch = []
    ed_view.batch_update()
    if ed_view.file != file:
        ed_view.open_file(file)
    pics_view = "edit"
    pictures_open()
    canvas.focus_set()

def edit_target():
    if at_groups() or not cards:
        return None
    for card in cards:
        if card[0] in marq_sel:
            return card[0]
    if sel_visible and sel_idx is not None:
        return cards[min(sel_idx, len(cards) - 1)][0]
    for card in cards:
        if str(card[0]) in keep_set:
            return card[0]
    return best_file_now() or cards[0][0]

def edit_current():
    file = edit_target()
    if file is not None:
        editor_open(file)

def bulk_files():
    if marq_sel:
        return [c[0] for c in cards if c[0] in marq_sel]
    return kept_now()

def key_edit():
    if at_groups() or not cards or not sel_visible or sel_idx is None:
        return
    editor_open(cards[sel_idx][0])

def edit_from_inspect(win):
    st = inspect_state.get(win)
    if st is None or st["file"] is None:
        return
    file = st["file"]
    canvas.after(10, lambda: editor_open(file))

def editor_key(event):
    if focus_in_text():
        return
    key = event.keysym.lower()
    if key == "c":
        ed_view.crop_start()
    elif key in ("return", "kp_enter"):
        ed_view.crop_end(True)
    elif key == "escape":
        if ed_view.crop_mode:
            ed_view.crop_end(False)
        else:
            editor_back()
    elif key in ("f1", "question"):
        keys_open()
    elif key in ("right", "space", "d") and ed_view.batch:
        ed_view.batch_step(1)
    elif key in ("left", "a") and ed_view.batch:
        ed_view.batch_step(-1)
    else:
        return
    return "break"

# ---- bulk editing
def bulk_look_get(label):
    look = ED_BUILTIN.get(label)
    if look is None:
        look = ed_presets.get(label[2:], {})
    out = {k: float(look.get(k, 0.0)) for k in ED_LOOK}
    out["hue"] = int(look.get("hue", 0))
    return out

def bulk_open(files=None):
    if execute_button.cget("state") == "disabled":
        messagebox.showinfo("Specorde", "Another task is still running. Try again when it has finished.")
        return
    live = editing() and ed_view.src is not None
    live_look = None
    if live:
        live_look = {k: ed_view.st[k] for k in ED_LOOK}
        live_look["hue"] = ed_view.st["hue"]
    win = ctk.CTkToplevel(canvas)
    win.withdraw()
    win.title("Bulk edit")
    win.configure(fg_color="#1f2029")
    win.resizable(False, False)
    win.transient(canvas)
    use_wm = tk.BooleanVar(master=win, value=bool(live and ed_view.st["wm_on"]))
    use_look = tk.BooleanVar(master=win, value=True)
    use_match = tk.BooleanVar(master=win, value=False)
    use_centre = tk.BooleanVar(master=win, value=False)
    use_geo = tk.BooleanVar(master=win, value=False)
    use_auto = tk.BooleanVar(master=win, value=True)
    use_prep = tk.BooleanVar(master=win, value=True)
    def go(chosen):
        if not chosen:
            return
        st = ed_copy(ED_DEFAULT)
        st["auto"] = use_auto.get()
        look = live_look if live else bulk_look_get(look_menu.get())
        if use_look.get():
            st.update(look)
        if live and use_geo.get():
            for key in ("turns", "flip_h", "flip_v", "angle"):
                st[key] = ed_view.st[key]
            st["crop"] = list(ed_view.st["crop"]) if ed_view.st["crop"] else None
        if use_centre.get():
            st["crop"] = None
        if use_wm.get():
            if not wm_ready() and not watermark_pick():
                return
            st["wm_on"] = True
            if live:
                st["wm_corner"] = ed_view.st["wm_corner"]
                st["wm_size"] = ed_view.st["wm_size"]
            else:
                st["wm_corner"] = wm_corner.get()
                try:
                    st["wm_size"] = min(60.0, max(1.0, float(wm_size.get())))
                except ValueError:
                    st["wm_size"] = 20.0
        target = None
        if use_match.get():
            try:
                if live:
                    ref = ed_view.src
                else:
                    ref = load_image(chosen[0], (640, 640))
                    ref.thumbnail((640, 640))
                target = ed_stats(ed_geometry(ref, st, use_centre.get()))
            except Exception:
                logging.exception("Could not measure the reference photo.")
        if st == ed_copy(ED_DEFAULT) and target is None and not use_centre.get() and not use_prep.get():
            messagebox.showinfo("Specorde", "Tick at least one option.", parent=win)
            return
        win.destroy()
        bulk_run(chosen, st, target, use_centre.get(), use_prep.get())

    def pick_files():
        picked = filedialog.askopenfilenames(parent=win, title="Choose photos", filetypes=[("Pictures", " ".join("*" + s for s in sorted(pic_suffixes))), ("All files", "*.*")])
        if picked:
            go([Path(c) for c in picked])

    ctk.CTkLabel(win, text="Bulk edit", font=(UI_FONT, 24)).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 2))
    ctk.CTkLabel(win, text="Copies go to 'edited_specorde' next to each photo. Originals are never changed.", font=(UI_FONT, 13), text_color="grey", wraplength=340, justify="left").grid(row=1, column=0, sticky="w", padx=20, pady=(0, 8))
    row = 2
    if live:
        match_text = "Match brightness to this photo (median)"
        look_text = "Apply this photo's look"
    else:
        match_text = "Match brightness to the first photo (median)"
        look_text = "Apply a look:"
    ctk.CTkCheckBox(win, text=look_text, variable=use_look, font=(UI_FONT, 14)).grid(row=row, column=0, sticky="w", padx=20, pady=3)
    row += 1
    look_menu = ctk.CTkOptionMenu(win, values=list(ED_BUILTIN) + ["★ " + n for n in ed_presets], font=(UI_FONT, 13), width=340, height=24, dynamic_resizing=False)
    look_menu.set("Normal")
    if not live:
        look_menu.grid(row=row, column=0, padx=20, pady=(0, 4))
        row += 1
    options = [("Auto-fix colour and brightness", use_auto), (match_text, use_match), ("Auto-centre on the subject (square crop)", use_centre)]
    if live:
        options.append(("Also apply this photo's crop and rotation", use_geo))
    for text, var in options:
        ctk.CTkCheckBox(win, text=text, variable=var, font=(UI_FONT, 14)).grid(row=row, column=0, sticky="w", padx=20, pady=3)
        row += 1
    ctk.CTkCheckBox(win, text="Add watermarks to every photo", variable=use_wm, font=(UI_FONT, 14)).grid(row=row, column=0, sticky="w", padx=20, pady=3)
    row += 1
    if not live:
        wm_row = ctk.CTkFrame(win, fg_color="transparent")
        wm_row.grid(row=row, column=0, sticky="w", padx=20, pady=(0, 4))
        row += 1
        wm_corner = ctk.CTkOptionMenu(wm_row, values=WM_CORNERS, font=(UI_FONT, 13), width=150, height=24, dynamic_resizing=False)
        wm_corner.set("Bottom Right")
        wm_corner.grid(row=0, column=0, padx=(0, 8))
        wm_size = ctk.CTkEntry(wm_row, width=50, justify="center")
        wm_size.insert(0, "20")
        wm_size.grid(row=0, column=1)
        ctk.CTkLabel(wm_row, text="% of photo width", font=(UI_FONT, 13), text_color="grey").grid(row=0, column=2, padx=6)
    sources = []
    if files:
        sources.append((f"These {len(files)} photos", files))
    if "target_folder" in globals():
        kept = kept_now()
        if kept:
            sources.append((f"Kept photos ({len(kept)})", kept))
        try:
            everything = sorted(p for p in target_folder.iterdir() if p.is_file() and p.suffix.lower() in pic_suffixes and not is_protected_item(p))
        except OSError:
            everything = []
        sources.append((f"All photos in the folder ({len(everything)})", everything))
    for text, chosen in sources:
        ctk.CTkButton(win, text=text, command=lambda c=chosen: go(c), state="normal" if chosen else "disabled", font=(UI_FONT, 14), width=340, height=28).grid(row=row, column=0, padx=20, pady=(8 if row == len(options) + 3 else 3, 3))
        row += 1
    ctk.CTkButton(win, text="Choose photos...", command=pick_files, font=(UI_FONT, 14), width=340, height=28).grid(row=row, column=0, padx=20, pady=3)
    row += 1
    if not live:
        pool = files or (kept_now() if "target_folder" in globals() else [])

        def to_editor():
            win.destroy()
            editor_open_batch(pool)

        ctk.CTkButton(win, text=f"Design the look in the editor ({len(pool)} photos)...", command=to_editor, state="normal" if pool else "disabled", font=(UI_FONT, 14), width=340, height=28, fg_color="#1f6aa5").grid(row=row, column=0, padx=20, pady=(10, 3))
        row += 1
    ctk.CTkButton(win, text="Cancel", command=win.destroy, font=(UI_FONT, 13), width=80, height=24, fg_color="#2c3043", hover_color="#3a4060").grid(row=row, column=0, sticky="e", padx=20, pady=(8, 16))
    win.after(300, lambda: set_inspect_icon(win))
    win.after(60, lambda: reveal(win))

def bulk_run(files, st, target, centre, prep=False):
    if execute_button.cget("state") == "disabled":
        messagebox.showinfo("Specorde", "Another task is still running. Try again when it has finished.")
        return
    n = len(files)
    if not messagebox.askyesno("Specorde", f"Edit {n} photo{'' if n == 1 else 's'}?\n\nNew copies go to 'edited_specorde' next to each photo. Your originals stay untouched.\n\nContinue?"):
        return
    lock_ui()
    start_execute(lambda: bulk_work(files, st, target, centre, prep))

def bulk_work(files, st, target, centre, prep=False):
    global pics_stamp
    q.put(("lock", None))
    q.put(("summary_clear", None))
    q.put(("bar_show", None))
    q.put(("bar_text_show", None))
    saved = 0
    failed = 0
    try:
        bar_start()
        total = len(files)
        plan = {}
        if prep:
            progress("Measuring photos...", 0, total)
            plan = ed_plan(files)
        for number, file in enumerate(files, start=1):
            if ed_export(file, st, target, centre, plan.get(file)).startswith("✓"):
                saved += 1
            else:
                failed += 1
            progress("Applying look...", number, total)
    except Exception:
        logging.exception("Bulk edit failed.")
        failed += 1
    finally:
        logging.info("Bulk edit: %d saved, %d failed.", saved, failed)
        text = f"✓ {saved} photo{'' if saved == 1 else 's'} saved to {ED_FOLDER}."
        if failed:
            text = f"✗ {saved} saved, {failed} failed."
        if "target_folder" in globals():
            pics_stamp = folder_stamp()
        q.put(("bar_set", 1))
        q.put(("bar_text", "100%"))
        q.put(("summary_add", text))
        q.put(("summary_hide_later", None))
        q.put(("status", "Bulk edit done!" if not failed else "Done with errors. See log..."))
        q.put(("status_reset", None))
        q.put(("bar_text_destroy", None))
        q.put(("bar_destroy", None))
        q.put(("unlock", None))

# ---- right-click menu and delete
def delete_one(file):
    global scan_order, pics_stamp
    if execute_button.cget("state") == "disabled":
        messagebox.showinfo("Specorde", "Another task is still running. Try again when it has finished.")
        return
    if not messagebox.askyesno("Specorde", f"Send '{file.name}' to the Recycle Bin?\n\nSpecorde can't restore files from the Recycle Bin.\n\nContinue?"):
        return
    try:
        send2trash(str(file))
    except Exception:
        logging.exception("Could not delete %s.", file.name)
        messagebox.showwarning("Specorde", "Could not delete this photo.")
        return
    logging.info("Deleted %s (Recycle Bin).", file.name)
    keep_set.discard(str(file))
    done_set.discard(str(file))
    keep_save()
    done_save()
    scan_order = [f for f in scan_order if f != file]
    photo_info.pop(file, None)
    pics_stamp = folder_stamp()
    inspect_close_all()
    compare_close()
    if open_idx is not None:
        rest = [f for f in groups[open_idx] if f != file]
        if rest:
            groups[open_idx] = rest
            group_open(open_idx, switching=True)
            return
    groups_build()
    groups_log()
    header_show()
    groups_show()

def pic_context(event):
    idx = card_at(event)
    if idx is None:
        if marq_sel:
            marq_clear()
        else:
            group_close()
        return
    if at_singles() and marq_sel and cards[idx][0] not in marq_sel:
        marq_clear()
    menu = tk.Menu(canvas, tearoff=0, bg="#1f2029", fg="#e6e8f0", activebackground="#1f6aa5", activeforeground="white", bd=0, relief="flat", font=(UI_FONT, 12))
    if at_groups():
        menu.add_command(label="Open group", command=lambda: group_open(idx))
        menu.add_command(label="Edit first photo", command=lambda: editor_open(cards[idx][0]))
    else:
        file = cards[idx][0]
        menu.add_command(label="Open", command=lambda: inspect_show(idx))
        menu.add_command(label="Edit", command=lambda: editor_open(file))
        menu.add_command(label="Unkeep" if str(file) in keep_set else "Keep", command=lambda: keep_flip(idx))
        menu.add_separator()
        menu.add_command(label="Bulk edit...", command=lambda: bulk_open(bulk_files()))
        menu.add_separator()
        menu.add_command(label="Delete...", command=lambda: delete_one(file))
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()

# ---- screen scale changes (moving the window to another monitor)
scale_seen = 1.0

def scale_watch():
    global scale_seen
    try:
        s = ui_scale()
        if abs(s - scale_seen) > 0.01:
            scale_seen = s
            schedule_refresh()
            ed_view.rescale()
    except Exception:
        logging.exception("scale_watch failed")
    canvas.after(700, scale_watch)

def resource_path(name):
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    return base / name


#tk
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Specorde.Specorde")
canvas = ctk.CTk()
def log_tk_error(exc, val, tb):
    logging.error("Unhandled error", exc_info=(exc, val, tb))
threading.excepthook = lambda args:logging.error("Thread crashed", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
canvas.report_callback_exception = log_tk_error
canvas.title("Specorde")

canvas_width, canvas_height = 1152, 648
try:
    dpi_scale = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
    room_w = canvas.winfo_screenwidth() - 40
    room_h = canvas.winfo_screenheight() - 120
    fit = min(room_w / (canvas_width * dpi_scale), room_h / (canvas_height * dpi_scale), 1)
    if fit < 1:
        ctk.set_window_scaling(fit)
        ctk.set_widget_scaling(fit)
        logging.info("Window scaled by %.2f to fit the screen.", fit)
except Exception:
    logging.exception("Could not fit the window to the screen.")
canvas.geometry("1152x648")
#plain bind on purpose, prevents clipping when dragging between monitors
canvas.bind("<Configure>", lambda event: None)
canvas.bind("<Key>", key_press)
canvas.bind("<KeyRelease>", key_release)
canvas.bind("<FocusOut>", key_reset)
canvas.resizable(width=False, height=False)
def on_close():
    if ed_view.dirty() and not messagebox.askyesno("Specorde", "You have unsaved edits. Quit anyway?"):
        return
    if execute_button.cget("state") == "disabled" and not messagebox.askyesno("Specorde", "A task is still running. Quit anyway?\n\nFiles already moved can be put back with 'Restore folder'."):
        return
    if keep_save_job is not None:
        keep_save()
    canvas.destroy()

canvas.protocol("WM_DELETE_WINDOW", on_close)
try:
    logo = ImageTk.PhotoImage(Image.open(str(resource_path("specorde_logo.ico"))))
    canvas.after(500, lambda: canvas.iconbitmap(str(resource_path("specorde_logo.ico"))))
    canvas.after(600, lambda: canvas.iconphoto(True, logo))
except Exception:
    logging.exception("Icon failed to load.")
check_messages()
clean_old_journals()

#left
left = ctk.CTkFrame(canvas, width=214, height=648, fg_color="#1f2029", corner_radius=0)
left.grid(row = 0, column = 0)
left.grid_propagate(False)
left.grid_columnconfigure(0, weight=1)
left.grid_rowconfigure(10, weight=1)

left_title = ctk.CTkLabel(left, text="Specorde", font=("Bahnschrift Light Condensed", 32))
left_title.grid(sticky="nw", pady=18, padx=18)

organize_button = ctk.CTkButton(left, text="Organize", font=("Bahnschrift Light Condensed", 16), command=organize_open)
organize_button.grid(sticky="nw", pady=(36, 18), padx=18)

culler_button = ctk.CTkButton(left, text="Pictures", font=("Bahnschrift Light Condensed", 16), command=pictures_open)
culler_button.grid(sticky="nw", pady=18, padx=18)

settings_button = ctk.CTkButton(left, text="Settings", font=("Bahnschrift Light Condensed", 16), command=settings_open)
settings_button.grid(sticky="nw", pady=18, padx=18)

tutorial_button = ctk.CTkButton(left, text="Tutorial", font=("Bahnschrift Light Condensed", 16), command=tutorial_open)
tutorial_button.grid(sticky="nw", pady=18, padx=18)
left_footer = ctk.CTkLabel(left, text=f"© 2026 Richard Vajko", text_color="grey", font=("Bahnschrift Light Condensed", 11), justify="left")
left_footer.grid(row=10, column=0, sticky="sw", pady=0, padx=12)

#middle
middle = ctk.CTkFrame(canvas, width=678, height=648, fg_color="#20222e", corner_radius=0)
middle.grid(row = 0, column = 1)
middle.grid_propagate(False)
middle.grid_columnconfigure(0, weight=1)
middle.grid_rowconfigure(10, weight=1)

#header
header = ctk.CTkFrame(middle, height=124, fg_color="#1f2028", corner_radius=0)
header.grid_rowconfigure(0, weight=1)
header.grid_columnconfigure(1, weight=1)
header.grid_columnconfigure(0, minsize=150)
folder_strip = ctk.CTkFrame(header, width=600, height=72, fg_color="transparent")
folder_browser = ctk.CTkButton(folder_strip, text="Choose a folder", command=pick_folder, font=("Bahnschrift Light Condensed", 18), width=124, height=29)
folder_chosen = ctk.CTkLabel(folder_strip, text="Folder:", text_color="grey", font=("Bahnschrift Light Condensed", 14), anchor="w", width=140)
folder_browser.place(x=314, y=22)
folder_chosen.place(x=444, y=22)


scale_probe = ctk.CTkFrame(middle, width=1000, height=10)
ed_view = Editor(middle)
ed_back_button = ctk.CTkButton(header, command=editor_back, text="Back to photos", font=("Bahnschrift Light Condensed", 13), width=100, height=14)
ed_name_label = ctk.CTkLabel(header, text="", text_color="grey", font=("Bahnschrift Light Condensed", 14))
canvas.bind("<Control-z>", lambda e: ed_view.do_undo() if editing() else None)
canvas.bind("<Control-y>", lambda e: ed_view.do_redo() if editing() else None)
canvas.bind("<Control-s>", lambda e: ed_view.save() if editing() else None)
canvas.bind("<Control-a>", lambda e: marq_all() if currently_open == 3 and pics_view == "grid" and at_singles() and not focus_in_text() else None)
overview_frame = ctk.CTkFrame(middle, width=view_w + 16, height=view_h_base, fg_color="#20222e", corner_radius=0)
overview_frame.grid_propagate(False)
overview_frame.grid_rowconfigure(0, weight=1)
overview_frame.grid_columnconfigure(0, weight=1)
grid_scale = ui_scale()
pic_canvas = tk.Canvas(overview_frame, width=round(view_w * grid_scale), height=round(view_h_base * grid_scale), bg="#20222e", highlightthickness=0, bd=0)
pic_scroll = ctk.CTkScrollbar(overview_frame, orientation="vertical", command=pic_canvas.yview)
pic_canvas.configure(yscrollcommand=on_yscroll)
pic_canvas.bind("<MouseWheel>", pic_wheel)
pic_canvas.bind("<Configure>", lambda event: schedule_refresh())
pic_canvas.bind("<ButtonPress-1>", pic_press)
pic_canvas.bind("<ButtonRelease-1>", pic_release)
pic_canvas.bind("<B1-Motion>", pic_drag)
pic_canvas.bind("<Button-3>", pic_context)
pic_canvas.bind("<Motion>", pic_hover)
pic_canvas.bind("<Leave>", lambda event: hover_clear())
pic_canvas.grid(row=0, column=0, sticky="nsew")
pic_scroll.grid(row=0, column=1, sticky="ns")
no_folder_label = ctk.CTkLabel(middle, text="No folder chosen yet.", font=("Bahnschrift Light Condensed", 28))
culler_loading = ctk.CTkLabel(middle, text="Reading photos...", font=("Bahnschrift Light Condensed", 28))
culler_empty = ctk.CTkLabel(middle, text="", text_color="grey", font=("Bahnschrift Light Condensed", 20), justify="center", wraplength=480)
cutesy_bar = ctk.CTkFrame(middle, height=34, width=652, fg_color="#1b1d27", corner_radius=0)
cutesy_bar.grid_propagate(False)
cutesy_bar.grid_columnconfigure(0, weight=1)
cutesy_bar.grid_rowconfigure(0, weight=1)
culler_label = ctk.CTkLabel(header, text="Pictures", font=("Bahnschrift Light Condensed", 32))
culler_mode_switch = ctk.CTkSegmentedButton(header, values=["All photos", "Groups"], command=pics_mode_set, font=(UI_FONT, 15), height=30, width=210, border_width=4, corner_radius=12, fg_color="#2c3043", unselected_color="#2c3043", selected_color="#1f6aa5", unselected_hover_color="#3a4060")
culler_mode_switch.set("All photos")
def tool_button(master, text, command, width, **extra):
    return ctk.CTkButton(master, text=text, command=command, font=(UI_FONT, 13), width=width, height=22, **extra)
bar_info = ctk.CTkLabel(cutesy_bar, text="", text_color="#9aa0b0", font=(UI_FONT, 14), anchor="w")
bar_info.grid(row=0, column=0, sticky="w", padx=(12, 6))
bar_keep_button = tool_button(cutesy_bar, "Keep", lambda: marq_keep(True), 50, fg_color="#2e8b57", hover_color="#37a367")
bar_unkeep_button = tool_button(cutesy_bar, "Unkeep", lambda: marq_keep(False), 60)
bar_clear_button = tool_button(cutesy_bar, "✕", marq_clear, 28, fg_color="#2c3043", hover_color="#3a4060")
bar_edit_button = tool_button(cutesy_bar, "Edit", edit_current, 48)
bar_bulk_button = tool_button(cutesy_bar, "Bulk edit (0)", lambda: bulk_open(bulk_files()), 112)
bar_wrap_button = tool_button(cutesy_bar, "Wrap up...", finish_open, 80)
bar_edit_button.grid(row=0, column=4, padx=(0, 6), pady=5)
bar_bulk_button.grid(row=0, column=5, padx=(0, 6), pady=5)
bar_wrap_button.grid(row=0, column=6, padx=(0, 10), pady=5)
culler_tools = ctk.CTkFrame(header, fg_color="transparent")
culler_camera_menu = ctk.CTkOptionMenu(culler_tools, values=["Camera"], command=camera_changed, font=(UI_FONT, 13), width=118, height=22, dynamic_resizing=False)
culler_groups_button = tool_button(culler_tools, "Groups: Normal", groups_cycle, 106)
culler_time_button = tool_button(culler_tools, "Dates: EXIF", time_toggle, 94)
culler_size_changer = tool_button(culler_tools, "Density: Medium", pictures_size, 110)
culler_sort_button = tool_button(culler_tools, "Sort: Name", sort_cycle, 92)
culler_finish_button = tool_button(culler_tools, "Wrap up...", finish_open, 82)
culler_groups_button.grid(row=0, column=1, padx=(0, 6))
culler_time_button.grid(row=0, column=2, padx=(0, 6))
culler_size_changer.grid(row=0, column=3, padx=(0, 6))
culler_finish_button.grid(row=0, column=4)
culler_group_tools = ctk.CTkFrame(header, fg_color="transparent")
culler_back_button = tool_button(culler_group_tools, "Back to groups", group_close, 98)
culler_info_label = ctk.CTkLabel(culler_group_tools, text="", text_color="grey", font=(UI_FONT, 14))
culler_suggest_button = tool_button(culler_group_tools, "No clear pick", key_suggest, 116, state="disabled", fg_color="#173348")
culler_compare_button = tool_button(culler_group_tools, "Compare (0)", compare_open, 88, state="disabled", fg_color="#173348")
culler_delete_button = tool_button(culler_group_tools, "Delete rest", delete_rest, 88, state="disabled", fg_color="#173348")
culler_clear_button = tool_button(culler_group_tools, "Clear kept", clear_kept, 84, state="disabled", fg_color="#173348")
culler_back_button.grid(row=0, column=0, padx=(0, 6))
culler_suggest_button.grid(row=0, column=1, padx=(0, 6))
culler_compare_button.grid(row=0, column=2, padx=(0, 6))
culler_delete_button.grid(row=0, column=3, padx=(0, 6))
culler_clear_button.grid(row=0, column=4, padx=(0, 6))

#tutorial
tutorial_label = ctk.CTkLabel(header, text="Tutorial", font=("Bahnschrift Light Condensed", 30))
tutorial_frame = ctk.CTkScrollableFrame(middle, width=590, height=470, fg_color="transparent")
tutorial_frame.grid_columnconfigure(0, weight=1)

tutorial_style = {
    "h1": (("Bahnschrift Light Condensed", 24), None, (0, 4), 6),
    "h2": (("Bahnschrift Light Condensed", 20), None, (16, 4), 6),
    "h3": (("Bahnschrift Light Condensed", 17), None, (8, 0), 12),
    "p": (("Bahnschrift Light Condensed", 15), "#aab0c0", (0, 2), 12),
}
tutorial_text = [
    ("h1", "Welcome to Specorde"),
    ("p", "Specorde tidies folders and helps you pick the best photos. It has two tools on the left, Organize and Culler. Everything it moves is written to a journal, so 'Restore folder' can put it back. Only files directly inside the chosen folder are used, not subfolders. Shortcuts, programs and hidden or system files are always skipped."),
    ("h2", "Organize"),
    ("p", "Choose a folder, tick what you want and press Execute. Progress shows in the Activity panel on the right."),
    ("h3", "Find duplicates"),
    ("p", "Finds identical files. In Settings, choose if they're moved to a 'duplicates_specorde' folder or sent to the Recycle Bin. Specorde cannot restore files from the Recycle Bin."),
    ("h3", "Sort files"),
    ("p", "Moves files into a 'sorted_specorde' folder by date. Choose date taken or date modified, and year/month or year/month/day. Date taken is read from JPEG, HEIC and most RAW files. Files without one use date modified."),
    ("h3", "Rename files"),
    ("p", "Gives your files new numbered names: original name + number, date + number, or your own name (up to 16 letters, numbers or underscores). Renaming twice with 'original name + number' adds a second number."),
    ("h3", "Preview and Restore"),
    ("p", "Preview shows what would happen without changing any file. Read the result in the log (Open log, bottom right). 'Restore folder' undoes the last run in the chosen folder, and pressing it again goes back to older runs. On USB drives, restoring needs the same drive letter."),
    ("h2", "Culler"),
    ("p", "The Culler helps you choose between similar photos. It reads JPEG, PNG, TIFF, WEBP, BMP, HEIC and most RAW files (RAW files are shown through the preview the camera saved inside them). Choose a folder and wait for the photos to be read. Photos taken close together by the same camera that look alike are stacked into groups. Photos that fit nowhere go into the 'Ungrouped' pile."),
    ("h3", "The overview"),
    ("p", "Click a group to open it. Hold the mouse button on a group to peek at its top photo, and let go to close the peek. Right-click or press 'Back to groups' to return. The blue number is how many photos are in a group, the green tick how many you kept."),
    ("h3", "Inside a group"),
    ("h3", "Groups and All photos"),
    ("p", "The switch next to the title changes the view. 'Groups' stacks similar photos. 'All photos' shows every picture on its own, sorted by name, date or camera. Compare, Delete rest and the sharpness hints only exist inside groups."),
    ("h3", "Selecting with a rectangle"),
    ("p", "Inside a group or in All photos, press and drag to draw a rectangle. Everything it touches is selected (blue frame). Hold Ctrl to add to the selection, and Ctrl+A selects everything. Press and hold without moving to peek instead. The bar at the bottom offers Keep, Unkeep, Edit and Bulk edit for the selection. Esc or a click on empty space clears it."),
    ("h3", "Bulk edit"),
    ("p", "Bulk edit applies one look to many photos and saves copies in 'edited_specorde'. Before editing it measures all the photos together: every photo is cropped square around the sleeve, and brightness, colour balance and saturation are pulled towards the average of the batch, using the floor as the reference, so one photo can no longer stand out. 'Match brightness' lifts dark photos and lowers bright ones to the same median level before the look is applied, so everything ends up consistent. 'Auto-centre' crops each photo square around the subject, which works best on a plain background. Find it in the bottom bar, the right-click menu and the editor."),
    ("p", "Click a photo, or the tick box in its corner, to keep it. Click again to un-keep it. Double-click a photo to open it in its own window; that window has a Keep button, and clicking the photo closes it. Hold the mouse button on a photo to peek at it larger."),
    ("h3", "Compare"),
    ("p", "Keep 2 to 4 photos, then press Compare. Side by side: scroll to zoom, drag to pan, double-click to jump to full size. All photos move together, so you can check sharpness or eyes in the same spot. Blink: click or Space flips between the photos in the same spot. Slider: move the mouse across to wipe between two shots. Highlights: coloured glow where shots differ. Photos are lined up first, so small camera shake is ignored. 'Keep this one' keeps that photo and un-keeps the other compared ones."),
    ("h3", "Delete rest"),
    ("p", "When a group has at least one kept and one not-kept photo, 'Delete rest' moves every photo you did not keep into a 'rejected_specorde' folder. Nothing is deleted for good, and 'Restore folder' in Organize puts the photos back. It is not available for the Ungrouped pile."),
    ("h3", "Clear kept"),
    ("p", "Un-keeps every photo in the open group, so you can start the group again."),
    ("h3", "Keyboard"),
    ("p", "In Compare: Q and E switch the view, A and D (or the arrows) step through photos, R or K keeps the shown photo."),
    ("p", "In Organize: 1, 2, 3 tick the functions, Enter runs, P toggles Preview, R restores, O picks a folder. In Settings: 1 and 2 switch pages. D, S, T, N and B cycle the dropdowns, and P cycles the watermark position (+ and - change its size)."),
    ("p", "Arrow keys move the yellow frame. Enter opens a group, or a photo in its own window. R or K keeps a photo. Space, Enter or Tab opens, and holding them peeks. Esc goes back. F marks a group finished. W A S D move like the arrows. B keeps the suggested sharpest photo. N finishes the group and jumps to the next unfinished one. C opens Compare."),
    ("h3", "Sharpness suggestion and Done"),
    ("p", "Inside a group, Specorde frames the sharpest photo in gold with a BEST star and marks clearly blurrier ones SOFT. The gold button in the top bar (or the B key) keeps the sharpest one for you. If all photos are equally sharp, or most are soft, it assumes that is on purpose and the button says 'No clear pick'. These are only hints: nothing is moved unless you press 'Delete rest'. Finished groups show a green FINISHED bar."),
    ("h3", "The buttons at the top"),
    ("p", "'Groups' sets how alike photos must be to share a group: Tight, Normal or Loose. The date button switches between EXIF dates (photos without one are hidden) and file dates. The camera menu shows one camera at a time. 'Density' changes the thumbnail size."),
    ("h2", "Settings"),
    ("p", "'Organizer Settings' has the options for duplicates, sorting and renaming. The 'Picture Modifier Settings' are for a feature that is not active yet."),
    ("h2", "Good to know"),
    ("p", "'Open log' (bottom right) shows what Specorde did and any problems it ran into. Your kept photos are remembered between sessions. Closing the app while a task runs is safe, because everything moved so far can be restored."),
]
for row, (kind, text) in enumerate(tutorial_text):
    font, color, pady, padx = tutorial_style[kind]
    ctk.CTkLabel(tutorial_frame, text=text, font=font, text_color=color, wraplength=540, justify="left", anchor="w").grid(row=row, column=0, sticky="w", padx=padx, pady=pady)

#settings
settings_label = ctk.CTkLabel(header, text="Settings", font=("Bahnschrift Light Condensed", 32))
find_settings = ctk.CTkFrame(middle, width=364, height=44, fg_color="#1f2029")
find_settings.grid_rowconfigure(2, weight=1)
find_settings.grid_propagate(False)
find_settings.grid_columnconfigure(1, weight=1)
sort_settings = ctk.CTkFrame(middle, width=364, height=88, fg_color="#1f2029")
sort_settings.grid_rowconfigure(2, weight=1)
sort_settings.grid_propagate(False)
sort_settings.grid_columnconfigure(1, weight=1)
rename_settings = ctk.CTkFrame(middle, width=364, height=44, fg_color="#1f2029")
rename_settings.grid_rowconfigure(1, weight=1)
rename_settings.grid_propagate(False)
rename_settings.grid_columnconfigure(2, weight=1)
rename_settings.grid_columnconfigure(1, minsize=40)

find_explain = ctk.CTkLabel(middle, text_color="grey", text="Finding duplicate files", font=("Bahnschrift Light Condensed", 13))
sort_explain = ctk.CTkLabel(middle, text_color="grey", text="Sorting files", font=("Bahnschrift Light Condensed", 13))
rename_explain = ctk.CTkLabel(middle, text_color="grey", text="Renaming files", font=("Bahnschrift Light Condensed", 13))
#Settings choice
settings_org_button = ctk.CTkButton(header, command=lambda: settings_change(0), text="Organizer Settings", font=("Bahnschrift Light Condensed", 13), width=112, height=14)
#Find Settings
settings_duplicate_delete_text = ctk.CTkLabel(find_settings, text="Duplicates are: ", font=("Bahnschrift Light Condensed", 16))
settings_duplicate_delete = ctk.CTkOptionMenu(find_settings, values=["Moved to a folder", "Deleted"], font=("Bahnschrift Light Condensed", 16), width=212, anchor="center")
settings_duplicate_delete.set("Moved to a folder")
settings_duplicate_delete_text.grid(padx=16, pady=8, row=0, column=0, sticky="w")
settings_duplicate_delete.grid(row=0, column=1, padx=16, pady=8, sticky="e")

#Sort Settings
settings_sort_structure_text = ctk.CTkLabel(sort_settings, text="Sorted structure: ", font=("Bahnschrift Light Condensed", 16))
settings_sort_structure = ctk.CTkOptionMenu(sort_settings, values=["year/month/day", "year/month"], font=("Bahnschrift Light Condensed", 16), width=212, anchor="center")
settings_sort_structure.set("year/month/day")

settings_sort_sortby_text = ctk.CTkLabel(sort_settings, text="Sort by: ", font=("Bahnschrift Light Condensed", 16))
settings_sort_sortby = ctk.CTkOptionMenu(sort_settings, values=["Date taken", "Date modified"], font=("Bahnschrift Light Condensed", 16), width=212, anchor="center")
settings_sort_sortby.set("Date taken")
settings_sort_sortby_text.grid(padx=16, pady=8, row=0, column=0, sticky="w")
settings_sort_sortby.grid(row=0, column=1, padx=16, pady=8, sticky="e")
settings_sort_structure_text.grid(padx=16, pady=8, row=1, column=0, sticky="w")
settings_sort_structure.grid(row=1, column=1, padx=16, pady=8, sticky="e")
#Rename Settings
def rename_pattern_changed(choice):
    global check
    if choice=="custom name + number":
        settings_rename_renameby.grid_forget()
        settings_rename_renameby_text.grid_forget()
        rename_settings.configure(height=96)
        custom_check_icon.grid(row=1, column=2, pady=8, sticky="e", padx=(0,235))
        settings_rename_custom_text.grid(padx=(16,155), pady=8, row=1, column=0, sticky="w")
        settings_rename_custom.grid(row=1, column=2, padx=(0,16), pady=8, sticky="e")
        custom_check()
    elif choice=="date + number":
        settings_rename_custom.grid_forget()
        settings_rename_custom_text.grid_forget()
        custom_check_icon.grid_forget()
        rename_settings.configure(height=96)
        settings_rename_renameby_text.grid(padx=(16,162), pady=8, row=1, column=0, sticky="w")
        settings_rename_renameby.grid(row=1, column=2, padx=(0,16), pady=8, sticky="e")
        check=1
    else:
        settings_rename_custom_text.grid_forget()
        custom_check_icon.grid_forget()
        settings_rename_custom.grid_forget()
        settings_rename_renameby_text.grid_forget()
        settings_rename_renameby.grid_forget()
        rename_settings.configure(height=44)
        check=1


def custom_check(event=None):
    global check
    text = settings_rename_custom.get('1.0', "end-1c")
    if len(text) > 16:
        check_text.configure(text="Your custom name can't have more than 16 characters!")
        custom_check_icon.configure(text="!")
        check = 0
    elif text == "":
        check_text.configure(text="Your custom name can't be empty!")
        custom_check_icon.configure(text="!")
        check = 0
    else:
        for char in text.lower():
            if char in (" ", "\n"):
                check_text.configure(text=f"Your custom name can't have a space or a new line!")
                custom_check_icon.configure(text="!")
                check = 0
                break
            elif char not in allowed_characters:
                check_text.configure(text=f"Your custom name can't have '{char}'!")
                custom_check_icon.configure(text="!")
                check = 0
                break
        else:
            check_text.configure(text=f"Your custom name is:  ' {text} '.")
            custom_check_icon.configure(text="✓")
            check = 1


settings_rename_custom_text = ctk.CTkLabel(rename_settings, text="Custom name: ", font=("Bahnschrift Light Condensed", 16))
settings_rename_custom = ctk.CTkTextbox(rename_settings, height=32, width=212)
settings_rename_renameby_text = ctk.CTkLabel(rename_settings, text="Rename by: ", font=("Bahnschrift Light Condensed", 16))
settings_rename_renameby = ctk.CTkOptionMenu(rename_settings, values=["Date taken", "Date modified"], font=("Bahnschrift Light Condensed", 16), width=212, anchor="center")
settings_rename_custom.bind("<KeyRelease>", custom_check)
settings_rename_pattern_text = ctk.CTkLabel(rename_settings, text="Renaming pattern: ", font=("Bahnschrift Light Condensed", 16))
settings_rename_pattern = ctk.CTkOptionMenu(rename_settings, values=["original name + number", "date + number", "custom name + number"], font=("Bahnschrift Light Condensed", 16), command=rename_pattern_changed, width=212, anchor="center")
settings_rename_pattern.set("original name + number")
settings_rename_pattern_text.grid(padx=16, pady=8, row=0, column=0, sticky="w")
settings_rename_pattern.grid(row=0, column=2, padx=16, pady=8, sticky="e")
custom_check_icon = ctk.CTkLabel(rename_settings, text="!", font=("Bahnschrift Light Condensed", 26), fg_color="#1c1c24", width=42, corner_radius=8)

check_display=ctk.CTkToplevel(canvas)
check_display.overrideredirect(True)
check_display.withdraw()
check_text = ctk.CTkLabel(check_display, text="Your custom name can't be empty!", font=("Bahnschrift Light Condensed", 16))
check_text.grid(padx=5, pady=2)

def show_display(event):
    check_display.geometry(f"+{event.x_root + 15}+{event.y_root + 15}")
    check_display.deiconify()
custom_check_icon.bind("<Motion>", show_display)
custom_check_icon.bind("<Leave>", lambda event: check_display.withdraw())

def dry_run_toggle():
    global dry_run
    if dry_run == 0:
        dry_run = 1
        execute_button.configure(text="Preview", text_color="#1f2029")
        q.put(("status", "Preview mode on."))
        logging.info("Preview (dry run) turned on")
    else:
        dry_run = 0
        execute_button.configure(text="Execute", text_color="white")
        q.put(("status", "Preview mode off."))
        logging.info("Preview (dry run) turned off")
    q.put(("status_reset", None))

#organize
organize_title = ctk.CTkLabel(header, text="Organize", font=("Bahnschrift Light Condensed", 30))
actions_title = ctk.CTkLabel(middle, text="Functions", text_color="grey", font=("Bahnschrift Light Condensed", 20))
actions_find = ctk.CTkCheckBox(middle, text="Find duplicates", font=("Bahnschrift Light Condensed", 16))
actions_water = ctk.CTkCheckBox(middle, text="Add watermark", font=("Bahnschrift Light Condensed", 16))
actions_sort = ctk.CTkCheckBox(middle, text="Sort files", font=("Bahnschrift Light Condensed", 16))
actions_rename = ctk.CTkCheckBox(middle, text="Rename files", font=("Bahnschrift Light Condensed", 16))
execute_button = ctk.CTkButton(middle, text="Execute", command=(run_execute), font=("Bahnschrift Light Condensed", 18), width=356, height=46)
footer = ctk.CTkFrame(middle, width=678, fg_color="#20222e")
footer.columnconfigure(0, weight=0)
file_disclaimer = ctk.CTkLabel(footer, text="DISCLAIMER: Cloud-only files are skipped. Files without a readable date taken use date modified.", text_color="grey",  font=("Bahnschrift Light Condensed", 11))
restore_button = ctk.CTkButton(footer, text="Restore folder", font=("Bahnschrift Light Condensed", 11), command=restore_click, width=76, height=24)
dry_run_button = ctk.CTkButton(footer, text="Preview", font=("Bahnschrift Light Condensed", 11), command=dry_run_toggle, width=52, height=24)

#show tutorial
if tutorial_seen == 0:
    tutorial_open()
    tutorial_seen = 1
    try:
        with open(memory, "w") as f:
            json.dump(tutorial_seen, f)
    except OSError:
        logging.exception("Could not save memory.json")
else:
    organize_open()

#right

right = ctk.CTkFrame(canvas, width=260, height=648, fg_color="#1f2029", corner_radius=0)
right.grid(row = 0, column = 2)
right.grid_propagate(False)
right.grid_columnconfigure(0, weight=1)
right.grid_rowconfigure(10, weight=1)
right_title = ctk.CTkLabel(right, text="Activity", font=("Bahnschrift Light Condensed", 30))
right_title.grid(sticky="nw", pady=18, padx=18)

status = ctk.CTkLabel(right, text="Sitting...", font=("Bahnschrift Light Condensed", 22), text_color="grey", fg_color="#1f2029", width=230, height=34, anchor="w")
status.grid(row=2, sticky="nw", padx=20)
bar_box = ctk.CTkFrame(right, width=230, height=60, fg_color="transparent")
bar_box.grid(row=3, column=0, sticky="nw")
bar_box.grid_propagate(False)
bar = ctk.CTkProgressBar(bar_box)
bar_text = ctk.CTkLabel(bar_box, text="")
q.put(("bar_hide", None))
q.put(("bar_text_hide", None))
bar_summary = ctk.CTkFrame(right, fg_color="transparent")
log_window = None

def close_log():
    global log_window
    if log_window is not None:
        try:
            log_window.destroy()
        except Exception: pass
        log_window = None

def set_log_icon():
    try:
        if log_window is not None and log_window.winfo_exists():
            log_window.iconbitmap(str(resource_path("specorde_logo.ico")))
    except Exception:
        logging.exception("Log window icon failed.")

def drop_topmost():
    try:
        if log_window is not None and log_window.winfo_exists():
            log_window.attributes("-topmost", False)
    except Exception:
        logging.exception("Could not reset topmost")

def open_log():
    global log_window
    if log_window is not None:
        close_log()
        return
    log_file = path / "specorde.log"
    if not log_file.exists():
        messagebox.showinfo("Specorde", "No log file has been created yet.")
        return
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-300:]
        log_window = ctk.CTkToplevel(canvas)
        log_window.title("Specorde log")
        log_window.geometry("720x420")
        log_window.protocol("WM_DELETE_WINDOW", close_log)
        box = ctk.CTkTextbox(log_window, wrap="word", font=("Consolas", 12))
        box.pack(fill="both", expand=True, padx=10, pady=10)
        box.insert("1.0", "".join(lines))
        box.see("end")
        box.configure(state="disabled")
        log_window.after(300, set_log_icon)
        log_window.attributes("-topmost", True)
        log_window.after(300, drop_topmost)
        log_window.focus_force()
    except Exception as e:
        logging.exception("Could not show log.")
        close_log()
        messagebox.showwarning("Specorde", f"Could not show the log.\n\n({e})")

#version
version_frame = ctk.CTkFrame(right, fg_color="transparent")
version_label = ctk.CTkLabel(version_frame, text=f"v{app_version}", text_color="grey", font=("Bahnschrift Light Condensed", 10))
log_button = ctk.CTkButton(version_frame, text="Open log", font=("Bahnschrift Light Condensed", 12), command=open_log, width=52, height=24)
version_frame.grid(row=11, column=0, sticky="sw", padx=0, pady=0)
version_label.grid(row=0, column=0, sticky="sw", padx=12)
log_button.grid(row=0, column=2, padx=(152,12), sticky="e", pady=6)

start_thumb_workers()
start_scan_workers()
thumb_poll()
scan_poll()
scale_watch()
canvas.mainloop()