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
from PIL import Image, ImageTk, ImageOps, ImageChops, ImageFilter, ImageStat
import json
import threading
import logging
from collections import Counter, OrderedDict
import queue
from send2trash import send2trash
import ctypes
from ctypes import wintypes
import io

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
    if target_folder.name in ("sorted_specorde", "duplicates_specorde", "rejected_specorde"):
        messagebox.showwarning("Specorde", "This is a Specorde output folder. Use 'Restore folder' to put its files back, or pick another folder.")
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
        "water": actions_water.get(),
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
            elif kind == "folder_reset":
                folder_browser.configure(text="Choose a new folder")
                folder_chosen.configure(text="Folder chosen:")
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

def watermark():
    try:
        ()
    except NameError:
        q.put(("status", "You must pick a folder."))

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
    folder_browser.configure(text="Choose a different folder")
    label_font = ctk.CTkFont(family="Bahnschrift Light Condensed", size=14)
    max_width = 165
    shown_name = target_folder.name or str(target_folder)
    shown_text = f"Folder chosen: '{shown_name}'"
    if label_font.measure(shown_text) > max_width:
        while shown_name and label_font.measure(f"Folder chosen: '{shown_name}...'") > max_width:
            shown_name = shown_name[:-1]
        shown_text = f"Folder chosen: '{shown_name.rstrip()}...'"
    folder_chosen.configure(text=shown_text)
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
if heif_ok:
    pic_suffixes |= heif_suffixes
if raw_ok:
    pic_suffixes |= raw_suffixes
view_w = 652
view_h_base = 492
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
photo_cache_file = path / "photo_cache.json"
photo_cache_max = 50000
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

def image_hash(gray):
    px = gray.tobytes()
    bits = 0
    for row in range(8):
        for col in range(8):
            i = row * 9 + col
            bits = (bits << 1) | (1 if px[i] > px[i + 1] else 0)
    return bits

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
    gray = load_image(file, (64, 64), mode="L").resize((9, 8), Image.BILINEAR, reducing_gap=2.0)
    if model:
        first = make.split()[0].lower() if make else ""
        if not first or model.lower().startswith(first):
            camera = model
        else:
            camera = f"{make} {model}"
    else:
        camera = make or None
    return stamp, camera, image_hash(gray)

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
    groups_build()
    groups_log()
    grid_clear()
    grid_update_region(grid_geometry())
    pic_canvas.yview_moveto(0)
    if currently_open == 3:
        header_show()
        empty_update()
    if culler_loading.winfo_manager():
        culler_loading.grid_forget()
        overview_frame.grid(row=1, column=0, sticky="ew")
        cutesy_bar.grid(row=2, column=0, sticky="ew")
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
group_limits = (6, 12, 20)
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

def similar(a, b, limit):
    if a is None or b is None:
        return False
    return bin(a ^ b).count("1") <= limit

def groups_build():
    global groups
    global cards
    global pending_pics
    global open_idx
    global other_idx
    global hidden_no_exif
    gap = group_gaps[group_level]
    limit = group_limits[group_level]
    by_camera = {}
    hidden_no_exif = 0
    for file in scan_order:
        if file in copy_hidden:
            continue
        info = photo_info.get(file)
        if info is None or info[4]:
            continue
        stamp, camera, dhash, modified, failed = info
        name = camera_of(file)
        if camera_choice != all_cameras and name != camera_choice:
            continue
        if time_mode == 1:
            stamp = modified
        elif stamp is None:
            hidden_no_exif += 1
            continue
        by_camera.setdefault(name, []).append((stamp, file.name.lower(), file, dhash))
    built = []
    for name, items in by_camera.items():
        items.sort(key=lambda t: (t[0], t[1]))
        current = None
        last_stamp = None
        last_hash = None
        first_hash = None
        for stamp, file_name, file, dhash in items:
            near = last_stamp is not None and stamp - last_stamp <= gap
            if current is not None and near and similar(last_hash, dhash, limit) and similar(first_hash, dhash, limit + 8):
                current[1].append(file)
            else:
                current = [stamp, [file]]
                built.append(current)
                first_hash = dhash
            last_stamp = stamp
            last_hash = dhash
    built.sort(key=lambda g: g[0])
    multi = [g[1] for g in built if len(g[1]) >= 2]
    singles = [g[1][0] for g in built if len(g[1]) == 1]
    groups = multi
    other_idx = None
    if singles:
        if ungrouped_first:
            groups = [singles] + multi
            other_idx = 0
        else:
            groups = multi + [singles]
            other_idx = len(groups) - 1
    cards = groups
    pending_pics = [g[0] for g in groups]
    open_idx = None
    time_button_update()

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

def time_button_update():
    if time_mode == 1:
        text = "File dates · all photos"
    elif hidden_no_exif:
        text = f"EXIF dates · {hidden_no_exif} hidden"
    else:
        text = "EXIF dates only"
    culler_time_button.configure(text=text)

def groups_show():
    grid_clear()
    grid_update_region(grid_geometry())
    pic_canvas.yview_moveto(0)
    empty_update()
    schedule_refresh()

def camera_changed(choice):
    global camera_choice
    if scan_active or copies_active:
        return
    camera_choice = choice
    groups_build()
    groups_log()
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
        culler_camera_menu.grid(row=1, column=0, sticky="w", padx=(16,8), pady=8)
    else:
        culler_camera_menu.grid_forget()

def header_show():
    if open_idx is None:
        culler_back_button.grid_forget()
        culler_group_tools.grid_forget()
        culler_tools.grid(row=1, column=1, sticky="e", padx=(0,12), pady=8)
        camera_menu_show()
    else:
        culler_tools.grid_forget()
        culler_camera_menu.grid_forget()
        culler_back_button.grid(row=1, column=0, sticky="w", padx=(16,8), pady=10)
        culler_group_tools.grid(row=1, column=1, sticky="e", padx=(0,12), pady=10)
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

def group_open(idx):
    global cards
    global pending_pics
    global open_idx
    global saved_top
    saved_top = pic_canvas.yview()[0]
    open_idx = idx
    cards = [[f] for f in groups[idx]]
    pending_pics = [c[0] for c in cards]
    culler_info_label.configure(text=group_title(idx))
    header_show()
    groups_show()
    inspect_preload(idx)

def group_close(event=None):
    global cards
    global pending_pics
    global open_idx
    if open_idx is None:
        return
    click_cancel()
    inspect_close_all()
    compare_close()
    peek_close()
    open_idx = None
    cards = groups
    pending_pics = [c[0] for c in cards]
    header_show()
    grid_clear()
    grid_update_region(grid_geometry())
    pic_canvas.yview_moveto(saved_top)
    schedule_refresh()

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
    font = ("Bahnschrift Light Condensed", -round(15 * s), "bold")
    if open_idx is None and idx == other_idx:
        bar_h = 24 * s
        items.append(pic_canvas.create_rectangle(left, top + h - bar_h, left + w, top + h, fill="#173348", outline=""))
        items.append(pic_canvas.create_text(left + w / 2, top + h - bar_h / 2, text=f"UNGROUPED · {len(card)}", fill="white", font=font))
    elif open_idx is None and len(card) >= 2:
        text = str(len(card))
        pill_draw(items, left + w - 6 * s - (14 + 8 * len(text)) * s, top + 6 * s, text, "#1f6aa5", s, font)
    if open_idx is None:
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

def card_redraw(idx):
    cell_remove(idx)
    cell_make(idx, grid_geometry())

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
    try:
        pics = [p for p in target_folder.iterdir() if p.is_file() and p.suffix.lower() in pic_suffixes]
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

def group_buttons_update():
    if open_idx is None:
        return
    kept, rest = group_kept_files()
    can_compare = 2 <= len(kept) <= 4
    culler_compare_button.configure(text=f"Compare ({len(kept)})", state="normal" if can_compare else "disabled", fg_color="#1f6aa5" if can_compare else "#173348")
    can_delete = bool(kept) and bool(rest)
    culler_clear_button.configure(state="normal" if kept else "disabled", fg_color="#1f6aa5" if kept else "#173348")
    culler_delete_button.configure(state="normal" if can_delete else "disabled", fg_color="#8b2e2e" if can_delete else "#173348")
    if open_idx == other_idx:
        culler_delete_button.grid_remove()
    else:
        culler_delete_button.grid()

def inspect_close(win):
    if win in inspect_windows:
        inspect_windows.remove(win)
    for key in [k for k, v in inspect_by_file.items() if v is win]:
        del inspect_by_file[key]
        inspect_buttons.pop(key, None)
    try:
        win.destroy()
    except Exception:
        pass

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
def inspect_show(idx, x=None, y=None):
    if idx >= len(cards):
        return
    file = cards[idx][0]
    existing = inspect_by_file.get(file)
    if existing is not None:
        try:
            if existing.winfo_exists():
                existing.lift()
                return
        except Exception:
            pass
    img = inspect_load(file)
    if img is None:
        return
    hover_clear()
    photo = ImageTk.PhotoImage(img)

    win = ctk.CTkToplevel(canvas)
    win.withdraw()
    win.title(file.name)
    win.configure(fg_color="#101117")
    win.resizable(False, False)
    win.transient(canvas)
    win.protocol("WM_DELETE_WINDOW", lambda: inspect_close(win))

    frame = tk.Frame(win, bg="#101117", highlightbackground=card_edge, highlightthickness=2, bd=0)
    frame.grid(row=0, column=0, padx=14, pady=(14, 6))
    label = tk.Label(frame, image=photo, bd=0, bg="#101117", cursor="hand2")
    label.image = photo
    label.grid(padx=5, pady=5)
    label.bind("<ButtonRelease-1>", lambda e: inspect_close(win))
    tk.Label(win, text=f"{file.name}   ·   click the photo to close", bg="#101117", fg="#c8ccd8", font=(UI_FONT, 12)).grid(row=1, column=0)

    def toggle():
        lock_toggle(file)
        keep_refresh(file)

    keep_button = ctk.CTkButton(win, text=keep_text(file), command=toggle, font=(UI_FONT, 16), width=120, height=30)
    keep_button.grid(row=2, column=0, pady=(8, 12))
    inspect_buttons[file] = keep_button
    
    if x is None:
        center_on_main(win, 28 * len(inspect_windows))
    else:
        place_at_mouse(win, x, y)
    inspect_windows.append(win)
    inspect_by_file[file] = win
    win.after(300, lambda: set_inspect_icon(win))
    win.after(60, lambda: reveal(win))

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

def pic_press(event):
    global press_job, press_idx, press_x, press_y, press_on_tick
    peek_close()
    press_idx = card_at(event)
    press_x = event.x_root
    press_y = event.y_root
    press_on_tick = open_idx is not None and press_idx is not None and tick_hit(event, press_idx)
    if press_idx is not None and not press_on_tick:
        press_job = pic_canvas.after(hold_ms, peek_start)

def pic_release(event):
    global press_job, press_idx, last_click_idx, last_click_time, press_on_tick
    if peek_window is not None:
        peek_close()
        press_idx = None
        press_on_tick = False
        return
    if press_job is not None:
        pic_canvas.after_cancel(press_job)
        press_job = None
    idx = card_at(event)
    started = press_idx
    on_tick = press_on_tick
    press_idx = None
    press_on_tick = False
    if idx is None or idx != started:
        return
    if open_idx is None:
        group_open(idx)
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
    if i is not None and (i, 0) in pic_cells:
        card_redraw(i)
    button = inspect_buttons.get(file)
    if button is not None:
        try:
            button.configure(text=keep_text(file))
        except Exception:
            inspect_buttons.pop(file, None)
    group_buttons_update()

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
    "Side by side": "Scroll to zoom, drag to pan, double-click to jump to full size. All photos move together. 'Keep this one' keeps that photo and un-keeps the other compared ones.",
    "Slider": "Move the mouse across the photo to wipe from one shot to the other.",
    "Highlights": "Coloured glow where the shots differ. Shots are lined up first, so camera shake is ignored.",
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
    view = tk.Frame(win, bg=PAD_COLOR)
    view.grid(row=1, column=0, padx=16, pady=4)
    caption = tk.Label(win, text="", bg=PAD_COLOR, fg="#c8ccd8", font=(UI_FONT, 12), wraplength=max_w, justify="center")
    caption.grid(row=2, column=0, pady=(2, 4))
    legend_frame = tk.Frame(win, bg=PAD_COLOR)
    legend_frame.grid(row=3, column=0, pady=(0, 12))
    state = {"mode": "Side by side", "blink": 0, "pair": 0, "label": None, "diff": None, "busy": False, "views": {}, "zoom": 1.0, "cx": 0.5, "cy": 0.5, "src": list(originals), "cells": [], "shown": [], "drag": None, "side_job": None}

    def blink_caption():
        i = state["blink"]
        caption.configure(text=f"Blink · {trim(names[i])} ({i + 1} of {n}) · click the photo or press Space to flip")

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
            ctk.CTkButton(view, text="Next pair", width=100, height=24, font=(UI_FONT, 14), command=next_pair).grid(row=1, column=0, pady=(8, 0))
        caption.configure(text=f"Slider · {trim(names[k])} on the left, {trim(names[k + 1])} on the right · {MODE_HELP['Slider']}")

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
                col = tk.Frame(view, bg=PAD_COLOR, highlightbackground=card_edge, highlightthickness=2, bd=0)
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
                ctk.CTkButton(col, text="Keep this one", width=100, height=22, font=(UI_FONT, 13), command=lambda f=f: choose(f)).grid(pady=6)
            state["cells"] = cells
            state["shown"] = [None] * n
            caption.configure(text=MODE_HELP[mode])
            side_schedule()
        elif mode == "Blink":
            lab = tk.Label(view, image=full_photos[state["blink"]], bd=0, bg=PAD_COLOR, cursor="hand2")
            lab.grid()
            lab.bind("<ButtonRelease-1>", flip)
            ctk.CTkButton(view, text="Keep this one", width=120, height=26, font=(UI_FONT, 14), command=lambda: choose(kept[state["blink"]])).grid(pady=(8, 0))
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
                if pct is not None:
                    info += " · nothing significant changed" if pct < 0.2 else f" · {pct:.1f}% of the picture changed"
                if shapes_differ:
                    info += " · the photos have different shapes, so treat this with care"
                caption.configure(text=info)
                for k, (color, label) in enumerate(legend):
                    tk.Label(legend_frame, text="   ", bg=color).grid(row=0, column=2 * k, padx=(10, 4))
                    tk.Label(legend_frame, text=label, bg=PAD_COLOR, fg="#c8ccd8", font=(UI_FONT, 12)).grid(row=0, column=2 * k + 1)
        center_on_main(win)

    def set_mode(value):
        state["mode"] = value
        draw()

    mode_bar = ctk.CTkSegmentedButton(modes, values=list(COMPARE_MODES), command=set_mode, font=(UI_FONT, 14))
    mode_bar.set(state["mode"])
    mode_bar.grid(row=0, column=0)

    win.bind("<space>", flip)
    win.bind("<Key-0>", side_reset)
    win.bind("<Escape>", compare_close)
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
    global journal_name, pics_stamp, scan_order
    kept, rest = group_kept_files()
    if open_idx is None or open_idx == other_idx or not kept or not rest:
        return
    if not messagebox.askyesno("Specorde", f"Keep {len(kept)}, move {len(rest)} others to '{rejected_name}'?\n\nYou can undo this with 'Restore folder' in Organize.\n\nContinue?"):
        return
    rejected = target_folder / rejected_name
    journal_path.mkdir(parents=True, exist_ok=True)
    journal_name = journal_path / f"run_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')}.jsonl"
    try:
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

def pictures_open():
    global currently_open
    global pending_pics
    global pics_folder
    global cards
    middle_reset()
    middle.grid_columnconfigure(0, weight=1)
    middle.grid_rowconfigure(8, weight=1)
    header.grid(column=0, row=0, sticky="ew", pady=(0,16))
    culler_label.grid(sticky="nw", pady=18, padx=18)
    folder_browser.grid(row=0, column=1, columnspan=2, sticky="e", pady=(24,18), padx=(4,240))
    folder_chosen.grid(row=0, column=1, columnspan=2, sticky="w", pady=(24,20), padx=(312,8))
    culler_size_label.grid(sticky="e", pady=8, padx=(0,95), column=2, row=1)
    culler_size_changer.grid(sticky="se", pady=10, padx=(8,16), column=2, row=1)
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
            cutesy_bar.grid(row=2, column=0, sticky="ew")
            empty_update()
            schedule_refresh()
    currently_open = 3

def pictures_size():
    global size
    old = grid_geometry()
    view_h = grid_view_h(old)
    mid = pic_canvas.canvasy(0) + view_h / 2
    t = max((mid - old["slot0"]) / old["pitch"], 0)
    anchor_row = int(t)
    anchor_frac = t - anchor_row
    anchor_index = anchor_row * old["per_row"]

    size = (size + 1) % 3
    culler_size_changer.configure(text=("Small", "Medium", "Large")[size])

    if not pending_pics:
        return
    new = grid_geometry()
    total = grid_update_region(new)
    new_mid = new["slot0"] + (anchor_index // new["per_row"] + anchor_frac) * new["pitch"]
    new_top = max(0, min(new_mid - view_h / 2, total - view_h))
    grid_clear()
    pic_canvas.yview_moveto(new_top / total)
    grid_refresh()

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
    folder_browser.grid(row=0, column=0, columnspan=2, sticky="e", pady=(24,18), padx=(4,240))
    folder_chosen.grid(row=0, column=0, columnspan=2, sticky="w", pady=(24,18), padx=(444,8))
    actions_title.grid(sticky="nw", padx=26, pady=(25,10), row=4)
    actions_find.grid(sticky="nw", padx=32, pady=(5,10), row=5)
    actions_sort.grid(sticky="nw", padx=32, pady=10, row=6)
    actions_rename.grid(sticky="nw", padx=32, pady=10, row=7)
    execute_button.grid(row=9, column=0, padx=104,pady=24)
    footer.grid(row=10, column=0, sticky="sw", padx=0, pady=(0,0))
    file_disclaimer.grid(row=0, column=0, sticky="sw", pady=0, padx=12)
    restore_button.grid(row=0, column=1, sticky="e", padx=(182, 60), pady=6)
    dry_run_button.grid(row=0, column=1, sticky="e", padx=(226, 0), pady=6)
    currently_open = 0 #(0 for organize, 1 for settings, 2 for tutorial)

def settings_open(option=0):
    global currently_open
    middle_reset()
    middle.grid_columnconfigure(0, weight=1)
    middle.grid_rowconfigure(8, weight=1)
    header.grid(column=0, row=0, sticky="ew", pady=(0,16))
    settings_label.grid(sticky="nw", pady=(18,0), padx=18, column=0, row=0)
    settings_file.grid(sticky="sw", pady=8, padx=(16,8), column=0, row=1)
    settings_pic.grid(sticky="sw", pady=8, padx=(8,0), column=1, row=1)
    folder_browser.grid(row=0, column=0, columnspan=2, sticky="e", pady=(24,18), padx=(4,240))
    folder_chosen.grid(row=0, column=0, columnspan=2, sticky="w", pady=(24,18), padx=(444,8))
    if option == 1:
        water_explain.grid(row=2, column=0, padx=20, pady=(5,0), sticky="w")
        water_settings.grid(row=3, column=0, padx=20, pady=(1,12), sticky="ew")
    else:
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
    folder_browser.grid(row=0, column=0, columnspan=2, sticky="e", pady=(24,18), padx=(4,240))
    folder_chosen.grid(row=0, column=0, columnspan=2, sticky="w", pady=(24,18), padx=(444,8))
    tutorial_frame.grid(row=1, column=0, sticky="nw", padx=(18, 6))
    currently_open = 2 #(0 for organize, 1 for settings, 2 for tutorial)

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
canvas.resizable(width=False, height=False)
def on_close():
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

culler_button = ctk.CTkButton(left, text="Culler", font=("Bahnschrift Light Condensed", 16), command=pictures_open)
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
folder_browser = ctk.CTkButton(header, text="Choose a folder", command=pick_folder, font=("Bahnschrift Light Condensed", 18), width=124, height=29)
folder_chosen = ctk.CTkLabel(header, text="Folder chosen:", text_color="grey", font=("Bahnschrift Light Condensed", 14), anchor="w")

scale_probe = ctk.CTkFrame(middle, width=1000, height=10)
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
pic_canvas.bind("<Button-3>", group_close)
pic_canvas.bind("<Motion>", pic_hover)
pic_canvas.bind("<Leave>", lambda event: hover_clear())
pic_canvas.grid(row=0, column=0, sticky="nsew")
pic_scroll.grid(row=0, column=1, sticky="ns")
no_folder_label = ctk.CTkLabel(middle, text="No folder chosen yet.", font=("Bahnschrift Light Condensed", 28))
culler_loading = ctk.CTkLabel(middle, text="Reading photos...", font=("Bahnschrift Light Condensed", 28))
culler_empty = ctk.CTkLabel(middle, text="", text_color="grey", font=("Bahnschrift Light Condensed", 20), justify="center", wraplength=480)
cutesy_bar = ctk.CTkFrame(middle, height = 8, fg_color="#20222e", width=652)
culler_label = ctk.CTkLabel(header, text="Culler", font=("Bahnschrift Light Condensed", 32))
culler_size_label = ctk.CTkLabel(header, text="Density: ", font=("Bahnschrift Light Condensed", 13))
culler_size_changer = ctk.CTkButton(header, command=pictures_size, text="Medium", font=("Bahnschrift Light Condensed", 13), width=77, height=14)
culler_tools = ctk.CTkFrame(header, fg_color="transparent")
culler_groups_button = ctk.CTkButton(culler_tools, command=groups_cycle, text="Groups: Normal", font=("Bahnschrift Light Condensed", 13), width=100, height=14)
culler_time_button = ctk.CTkButton(culler_tools, command=time_toggle, text="EXIF dates only", font=("Bahnschrift Light Condensed", 13), width=150, height=14)
culler_groups_button.grid(row=0, column=0, padx=(0,8))
culler_time_button.grid(row=0, column=1)
culler_back_button = ctk.CTkButton(header, command=group_close, text="Back to groups", font=("Bahnschrift Light Condensed", 13), width=100, height=14)
culler_group_tools = ctk.CTkFrame(header, fg_color="transparent")
culler_info_label = ctk.CTkLabel(culler_group_tools, text="", text_color="grey", font=("Bahnschrift Light Condensed", 14))
culler_compare_button = ctk.CTkButton(culler_group_tools, command=compare_open, text="Compare (0)", font=("Bahnschrift Light Condensed", 13), width=90, height=14, state="disabled", fg_color="#173348")
culler_delete_button = ctk.CTkButton(culler_group_tools, command=delete_rest, text="Delete rest", font=("Bahnschrift Light Condensed", 13), width=90, height=14, state="disabled", fg_color="#173348")
culler_info_label.grid(row=0, column=0, padx=(0,12))
culler_compare_button.grid(row=0, column=1, padx=(0,8))
culler_delete_button.grid(row=0, column=2)
culler_clear_button = ctk.CTkButton(culler_group_tools, command=clear_kept, text="Clear kept", font=("Bahnschrift Light Condensed", 13), width=76, height=14, state="disabled", fg_color="#173348")
culler_clear_button.grid(row=0, column=3, padx=(8, 0))
culler_camera_menu = ctk.CTkOptionMenu(header, values=["Camera"], command=camera_changed, font=("Bahnschrift Light Condensed", 13), width=126, height=22, dynamic_resizing=False)

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
    ("p", "Click a photo, or the tick box in its corner, to keep it. Click again to un-keep it. Double-click a photo to open it in its own window; that window has a Keep button, and clicking the photo closes it. Hold the mouse button on a photo to peek at it larger."),
    ("h3", "Compare"),
    ("p", "Keep 2 to 4 photos, then press Compare. Side by side: scroll to zoom, drag to pan, double-click to jump to full size. All photos move together, so you can check sharpness or eyes in the same spot. Blink: click or Space flips between the photos in the same spot. Slider: move the mouse across to wipe between two shots. Highlights: coloured glow where shots differ. Photos are lined up first, so small camera shake is ignored. 'Keep this one' keeps that photo and un-keeps the other compared ones."),
    ("h3", "Delete rest"),
    ("p", "When a group has at least one kept and one not-kept photo, 'Delete rest' moves every photo you did not keep into a 'rejected_specorde' folder. Nothing is deleted for good, and 'Restore folder' in Organize puts the photos back. It is not available for the Ungrouped pile."),
    ("h3", "Clear kept"),
    ("p", "Un-keeps every photo in the open group, so you can start the group again."),
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
water_settings = ctk.CTkFrame(middle, width=364, height=64, fg_color="#1f2029")
water_settings.grid_rowconfigure(3, weight=1)
water_settings.grid_propagate(False)
water_settings.grid_columnconfigure(1, weight=1)
rename_settings = ctk.CTkFrame(middle, width=364, height=44, fg_color="#1f2029")
rename_settings.grid_rowconfigure(1, weight=1)
rename_settings.grid_propagate(False)
rename_settings.grid_columnconfigure(2, weight=1)
rename_settings.grid_columnconfigure(1, minsize=40)

find_explain = ctk.CTkLabel(middle, text_color="grey", text="Finding duplicate files", font=("Bahnschrift Light Condensed", 13))
sort_explain = ctk.CTkLabel(middle, text_color="grey", text="Sorting files", font=("Bahnschrift Light Condensed", 13))
rename_explain = ctk.CTkLabel(middle, text_color="grey", text="Renaming files", font=("Bahnschrift Light Condensed", 13))
water_explain = ctk.CTkLabel(middle, text_color="grey", text="Adding watermarks", font=("Bahnschrift Light Condensed", 13))

#Settings choice
settings_file = ctk.CTkButton(header, command=lambda: settings_change(0), text="Organizer Settings", font=("Bahnschrift Light Condensed", 13), width=112, height=14)
settings_pic = ctk.CTkButton(header, command=lambda: settings_change(1), text="Picture Modifier Settings", font=("Bahnschrift Light Condensed", 13), width=112, height=14)

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
#Watermark Settings

settings_watermark_image_text = ctk.CTkLabel(water_settings, text="Watermark image: ", font=("Bahnschrift Light Condensed", 16))
settings_watermark_image = ctk.CTkButton(water_settings, width=212, text="Choose an image", font=("Bahnschrift Light Condensed", 16), command=filedialog.askopenfile)
settings_watermark_corner_text = ctk.CTkLabel(water_settings, text="Watermark position: ", font=("Bahnschrift Light Condensed", 16))
settings_watermark_corner = ctk.CTkOptionMenu(water_settings, values=["Top Right", "Top Left", "Bottom Right", "Bottom Left", "Centre"], font=("Bahnschrift Light Condensed", 16), width=212, anchor="center")
settings_watermark_corner.set("Top Right")

watermark_size_frame = ctk.CTkFrame(water_settings, fg_color="transparent")
watermark_size_frame.grid_columnconfigure(1, weight=1)
settings_watermark_size_text = ctk.CTkLabel(watermark_size_frame, text="Watermark size: ", font=("Bahnschrift Light Condensed", 16))
watermark_size_frame.grid(row=2,column=0, sticky="ew", columnspan=2)
last_good=20
def size_check(event=None):
    global last_good
    try:
        if int(settings_watermark_size.get()) < 1 or int(settings_watermark_size.get()) > 150:
            settings_watermark_size.delete(0, "end")
            settings_watermark_size.insert(0, last_good)

        else:
            last_good = settings_watermark_size.get()
    except ValueError:
        settings_watermark_size.delete(0, "end")
        settings_watermark_size.insert(0,last_good)

watermark_size_subframe = ctk.CTkFrame(watermark_size_frame, fg_color="transparent")
watermark_size_subframe.grid_columnconfigure(2, weight=1)
watermark_size_subframe.grid(column = 1, row=0, sticky="e")

settings_watermark_size = ctk.CTkEntry(watermark_size_subframe, justify="center", width=104)
settings_watermark_size.bind("<FocusOut>", size_check)
settings_watermark_size.insert(0, "20")
settings_watermark_image_text.grid(padx=16, pady=8, row=0, column=0, sticky="w")
settings_watermark_image.grid(row=0, column=1, padx=16, pady=8, sticky="e")
settings_watermark_corner_text.grid(padx=16, pady=8, row=1, column=0, sticky="w")
settings_watermark_corner.grid(row=1, column=1, padx=16, pady=8, sticky="e")
settings_watermark_size_text.grid(padx=16, pady=8, row=0, column=0, sticky="w")

def minus():
    global last_good
    try:
        updated = int(settings_watermark_size.get()) - 1
        if updated < 1:
            return
        else:
            last_good=updated
        settings_watermark_size.delete(0, "end")
        settings_watermark_size.insert(0, str(last_good))
    except ValueError:
        settings_watermark_size.delete(0, "end")
        settings_watermark_size.insert(0, str(last_good))
def plus():
    global last_good
    try:
        updated = int(settings_watermark_size.get()) + 1
        if updated > 150:
            return   
        else:
            last_good=updated
        settings_watermark_size.delete(0, "end")
        settings_watermark_size.insert(0, str(updated))
    except ValueError:
        settings_watermark_size.delete(0, "end")
        settings_watermark_size.insert(0, str(last_good))


set_wat_minus = ctk.CTkButton(watermark_size_subframe, text="-", command=minus, font=("Bahnschrift Light Condensed", 16), width=49)
set_wat_plus = ctk.CTkButton(watermark_size_subframe, text="+", command=plus, font=("Bahnschrift Light Condensed", 16), width=49)
set_wat_minus.grid(row=0,column=0, padx=(65,0), sticky="w")
settings_watermark_size.grid(row=0, column=1, padx=5, pady=8, sticky="w")
set_wat_plus.grid(row=0,column=2, padx=(0,16), sticky="w")

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
canvas.mainloop()