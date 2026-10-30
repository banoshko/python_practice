#This is my attempt at making an actually sellable product.
#Not even 2 weeks into python at this point
#Start - Sunday, 27th Sep. 2026

from datetime import datetime
from pathlib import Path
import hashlib
import os
import sys
import customtkinter as ctk
import time
import re
import tempfile
from logging.handlers import RotatingFileHandler
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import json
import threading
import logging
from collections import Counter
import queue
from send2trash import send2trash
import ctypes

#version
app_version = "1.0.1.0"

#Developer settings
month_dict = {
    1: "01 January", 2: "02 February", 3: "03 March", 4: "04 April", 5: "05 May", 6: "06 June", 7: "07 July", 8: "08 August", 9: "09 September", 10: "10 October", 11: "11 November", 12: "12 December"
}
suffix = [
    "(1)", "(2)", "(3)", "(4)", "(5)", "(6)", "(7)", "(8)", "(9)", "(10)", "(11)", "(12)", "(13)", "(14)", "(15)", "(16)", "(17)", "(18)", "(19)", "(20)", "- Copy"
]
q = queue.Queue()
cfg = {}
check = 1
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

log_handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s", "%H:%M:%S"))
logging.basicConfig(level=logging.INFO, handlers=[log_handler])
logging.info("Specorde %s started", app_version)
def log_crash(exc, val, tb):
    logging.critical("Crashed", exc_info=(exc, val, tb))
sys.excepthook = log_crash
memory = path / "memory.json"
journal_path = path / "journals"
journal_name = None
size = 1
dry_run = 0

tutorial_seen = 0
try:
    with open(memory, "r", encoding="utf-8") as f:
        tutorial_seen = json.load(f)
except FileNotFoundError:
    logging.info("memory.json not found, starting fresh")
except (OSError, json.JSONDecodeError):
    logging.warning("memory.json unreadable, starting fresh")
if tutorial_seen not in (0, 1):
    tutorial_seen = 0

if tutorial_seen == 0:
    currently_open = 1
else:
    currently_open = 0  

exif_suffix = {".jpg", ".jpeg", ".tiff", ".tif", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2"}
#Script itself
def start_execute(task):
    threading.Thread(target=task, daemon=True).start()

def lock_ui():
    for b in (execute_button, folder_browser, restore_button, dry_run_button):
        b.configure(fg_color="#173348", state="disabled")

def run_execute():
    global cfg
    if "target_folder" not in globals():
        q.put(("status", "You must pick a folder"))
        q.put(("status_reset", None))
        return
    
    if not (actions_find.get() or actions_sort.get() or actions_rename.get()):
        q.put(("status", "Tick at least one function"))
        q.put(("status_reset", None))
        return
    if actions_rename.get() and settings_rename_pattern.get() == "custom name + number":
        custom_check()
        if check == 0:
            messagebox.showwarning("Specorde", "Your custom name is not valid. Check it in Settings")
            return
    if not target_folder.is_dir():
        messagebox.showwarning("Specorde", "That folder no longer exists. Please choose it again")
        return
    if not dry_run:
        try:
            count = sum(1 for f in target_folder.iterdir() if f.is_file() and not is_protected_item(f))
        except OSError:
            messagebox.showwarning("Specorde", "Can't read that folder. Please pick another folder")
            return
        message = f"This will change files in '{target_folder.name}' ({count} files)"
        if actions_find.get() and settings_duplicate_delete.get() == "Deleted":
            message += "\n\nDuplicates will be sent to the Recycle Bin. On USB or network drives they may be deleted permanently"
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
    finally: canvas.after(20, check_messages)

def parse_exif_date(text):
    try:
        return datetime.strptime(text, "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None

def mark():
    return "○ " if dry_run else "✓ "

def result(count, thing, verb, failed=0):
    """One summary line: '✓ 3 duplicates moved' or '○ 3 duplicates would be moved'"""
    n = f"{count} {thing}" + ("" if count == 1 else "s")
    text = f"{n} would be {verb}" if dry_run else f"{n} {verb}"
    if failed:
        text += f" ({failed} failed)"
    return mark() + text

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
    # Write the journal entry BEFORE moving. If this fails, the file is not touched.
    try:
        with open(journal_name, "a", encoding="utf-8") as f:
            f.write(json.dumps({"from": str(item), "to": str(destination)}) + "\n")
    except OSError:
        logging.exception("Could not write journal, leaving %s untouched", item.name)
        return False
    try:
        item.rename(destination)
    except OSError:
        logging.exception("Could not move or rename %s", item.name)
        return False
    logging.debug("Moved %s -> %s", item.name, short(destination))
    return True

def remove_duplicate(file, mode):
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

def get_exif(path):
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
            logging.warning("No date taken for %s, using date modified instead", item.name)
        else:
            logging.debug("%s has an unsupported suffix, using date modified", item.name)
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
        return mark() + "No files to sort"
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
        progress("Finding duplicates", done, total)

        if sizes[item_size] < 2:
            continue
        try:
            file_hash = get_hash(item)
        except OSError:
            logging.exception("Could not read %s", item.name)
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
            logging.exception("Could not remove duplicate %s", item.name)
            failed += 1

    q.put(("bar_set", 1))
    q.put(("bar_text", "100%"))
    if removed == 0 and failed == 0:
        old = mode == "Moved to a folder" and duplicates.exists() and any(duplicates.iterdir())
        return mark() + ("No new duplicates found" if old else "No duplicates found")
    verb = "moved" if mode == "Moved to a folder" else "removed"
    return result(removed, "duplicate", verb, failed)


def rename():
    if check == 0:
        return "✗ Custom name is not valid"
    choice = cfg["pattern"]
    renameby = cfg["renameby"]
    custom = cfg["custom"]

    files = sorted(list_files(target_folder), key=lambda t: t[0].name.lower())
    if not files:
        return mark() + "No files to rename"
    total = sum(s for _, s in files) or 1
    done = 0
    width = len(str(len(files)))
    renamed = 0
    failed = 0
    bar_start()

    for number, (item, item_size) in enumerate(files, start=1):
        done += item_size
        progress("Renaming the files", done, total)
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
        q.put(("status", "You must pick a folder"))

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
            if f.is_file() and not is_protected_item(f):
                files.append((f, f.stat().st_size))
        except OSError:
            continue
    return files

def is_dangerous(folder):
    folder = folder.resolve()
    home = Path.home().resolve()
    if folder == Path(folder.anchor) or folder == home or folder == home.parent:
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
        messagebox.showwarning("Specorde", "Can't access that folder. Please pick another folder")
        return
    if dangerous:
        messagebox.showwarning("Specorde", "This folder is protected and can't be organized. Please pick another folder")
        return
    target_folder = Path(chosen)
    folder_browser.configure(text="Choose a different folder")

    label_font = ctk.CTkFont(family="Bahnschrift Light Condensed", size=14)
    max_width = 165
    shown_name = target_folder.name
    shown_text = f"Folder chosen: '{shown_name}'"
    if label_font.measure(shown_text) > max_width:
        while shown_name and label_font.measure(f"Folder chosen: '{shown_name}...'") > max_width:
            shown_name = shown_name[:-1]
        shown_text = f"Folder chosen: '{shown_name.rstrip()}...'"
    folder_chosen.configure(text=shown_text)

    sorted_dir = Path(target_folder/"sorted_specorde")
    duplicates = Path(target_folder/"duplicates_specorde")
    q.put(("status", "Folder ready!"))
    q.put(("status_reset", None))
    q.put(("unlock", None))
    

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
    final_status = "Preview done! See log..." if dry_run else "Done!"
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
                line = f"✗ {label} failed (see log)"
            q.put(("summary_add", line))
            logging.info("%s: %s  (%.1f s)", label, line[2:], time.perf_counter() - step_started)
    except Exception:
        logging.exception("Error trying to execute")
        final_status = "Something went wrong. See log..."
    finally:
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
        return "○ Nothing to restore"
    n = f"{count} change" + ("" if count == 1 else "s")
    text = f"{n} undone"
    extra = []
    if missing:
        extra.append(f"{missing} missing")
    if failed:
        extra.append(f"{failed} failed")
    if extra:
        text += " (" + ", ".join(extra) + ")"
    return ("✗ " if failed or missing else "✓ ") + text

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
                    logging.error("Could not restore %s", item.name)
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
                        logging.error("Could not restore %s", month_sub.name)
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
                            logging.error("Could not restore %s", item.name)
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
            logging.error("Journal contains a path outside the selected folder: %r", entry)
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
            logging.error("Could not restore %s", moved_to.name)
            restore_stats["failed"] += 1
    return moved

def start_restoring():
    global target_folder
    entries = []
    parse_errors = 0
    moved = 0
    duplicates_moved = 0
    targed_folder_remove = 0
    if "target_folder" not in globals():
        q.put(("status", "You must pick a folder"))
        q.put(("status_reset", None))
        return
    q.put(("lock", None))
    try:

        journal_file = find_last_run()
        if journal_file is None:
            if not duplicates.exists() and not sorted_dir.exists():
                if target_folder.name != "sorted_specorde" and target_folder.name != "duplicates_specorde":
                    q.put(("status", "Nothing to restore..."))
                    q.put(("status_reset", None))
                    return
        if not target_folder.is_dir():
            q.put(("status", "Your chosen folder no longer exists."))
            q.put(("status_reset", None))
            return

        elif not journal_file is None:
            q.put(("status", "Restoring..."))
            with open(journal_file, "r", encoding="utf-8") as f:
                f.readline()
                for line_number, line in enumerate(f, start=2):
                    try:
                        item = json.loads(line)
                        entries.append(item)
                    except json.JSONDecodeError:
                        logging.exception("Invalid journal entry on line %d", line_number)
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
            targed_folder_remove = 1
            if moved:
                q.put(("status", "Everything back in its place!"))
            else:
                q.put(("status", "Nothing to restore..."))
            q.put(("status_reset", None))

        elif target_folder.name == "duplicates_specorde":
            moved = restore_duplicates(target_folder, target_folder.parent)
            targed_folder_remove = 1
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
                q.put(("status", "Restored, some files were missing" if restore_stats["missing"] else "Everything back in its place!"))
            elif restore_stats["missing"]:
                q.put(("status", "Restore incomplete: files are missing"))
            else:
                q.put(("status", "Nothing to restore..."))
            q.put(("status_reset", None))

        total_moved = moved + duplicates_moved
        failed = restore_stats["failed"]
        logging.info("Restore finished: %d undone, %d failed", total_moved, failed)
        q.put(("bar_set", 1))
        q.put(("bar_text", "100%"))
        if failed:
            q.put(("status", "Restored with errors. See log."))
            q.put(("status_reset", None))
        q.put(("summary_add", restore_line(total_moved, failed, restore_stats["missing"])))
        q.put(("summary_hide_later", None))

        if journal_file is not None and not failed and not restore_stats["missing"]:
            try:
                journal_file.rename(journal_file.with_suffix(".used"))
            except OSError:
                logging.exception("Could not mark journal as used; keeping it for recovery")

        if targed_folder_remove == 1:
            try:
                target_folder.rmdir()
                del target_folder
                q.put(("folder_reset", None))
            except OSError: pass
    except Exception:
        logging.exception("Restore failed")
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
    if not messagebox.askyesno("Specorde", f"Put the files in '{target_folder.name}' back where they were before the last run?\n\nFiles sent to the Recycle Bin can't be restored by Specorde.\n\nContinue?"):
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
    folder_chosen.grid(row=0, column=0, columnspan=2, sticky="w", pady=(24,18), padx=(442,8))
    actions_title.grid(sticky="nw", padx=26, pady=(25,10), row=4)
    actions_find.grid(sticky="nw", padx=32, pady=(5,10), row=5)
    actions_sort.grid(sticky="nw", padx=32, pady=10, row=6)
    actions_rename.grid(sticky="nw", padx=32, pady=10, row=7)
    execute_button.grid(row=9, column=0, padx=104,pady=24)
    footer.grid(row=10, column=0, sticky="sw", padx=14, pady=(0,4))
    file_disclaimer.grid(row=0, column=0, sticky="w", pady=2, padx=8)
    restore_button.grid(row=0, column=1, sticky="e", padx=(250, 60), pady=8)
    dry_run_button.grid(row=0, column=1, sticky="e", padx=(365, 0), pady=8)
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
    folder_chosen.grid(row=0, column=0, columnspan=2, sticky="w", pady=(24,18), padx=(442,8))
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
    folder_chosen.grid(row=0, column=0, columnspan=2, sticky="w", pady=(24,18), padx=(442,8))
    tutorial_frame.grid(row=1, column=0, sticky="nw", padx=18)
    currently_open = 2 #(0 for organize, 1 for settings, 2 for tutorial)

def pictures_open(option=0):
    global middle
    global currently_open
    middle_reset()
    middle.grid_columnconfigure(0, weight=1)
    middle.grid_rowconfigure(8, weight=1)
    header.grid(column=0, row=0, sticky="ew", pady=(0,16))
    pictures_label.grid(sticky="nw", pady=(18,0), padx=18, column=0, row=0)
    folder_browser.grid(row=0, column=1, columnspan=2, sticky="e", pady=(24,18), padx=(4,240))
    folder_chosen.grid(row=0, column=1, columnspan=2, sticky="w", pady=(24,18), padx=(304,8))
    pictures_overview.grid(sticky="sw", pady=8, padx=(16,8), column=0, row=1)
    pictures_culling.grid(sticky="sw", pady=8, padx=(8,0), column=1, row=1)
    pictures_size_label.grid(sticky="e", pady=8, padx=(0,95), column=2, row=1)
    pictures_size_changer.grid(sticky="se", pady=10, padx=(8,16), column=2, row=1)
    try:
        if option == 0:
            culling_frame.grid_forget()
            overview_frame.grid(row=2, column=0, sticky="ew")
            for pic in target_folder.iterdir():
                if pic.is_file() and pic.suffix in [".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"]:
                    ()
        elif option == 1:
            overview_frame.grid_forget()
            culling_frame.grid(row=2, column=0, sticky="ew")
    except NameError:
        no_folder_chosen_error = ctk.CTkLabel(middle, text="No folder chosen yet.", font=("Bahnschrift Light Condensed", 28))
        no_folder_chosen_error.grid(row=1, pady=20)
    currently_open = 3

def pictures_change(option=0):
    pictures_open(option)

def pictures_size():
    global size
    if size != 2:
        size +=1
    else:
        size=0
    if size==0:
        pictures_size_changer.configure(text="Small")
        per_row = 6
    elif size==1:
        pictures_size_changer.configure(text="Medium")
        per_row = 4
    else:
        pictures_size_changer.configure(text="Large")
        per_row = 3
    #return pic_width, pic_height

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
canvas.geometry("1152x648")
canvas.resizable(width=False, height=False)
def on_close():
    if execute_button.cget("state") == "disabled" and not messagebox.askyesno("Specorde", "A task is still running. Quit anyway?\n\nFiles already moved can be put back with 'Restore folder'."):
        return
    canvas.destroy()

canvas.protocol("WM_DELETE_WINDOW", on_close)
try:
    logo = ImageTk.PhotoImage(Image.open(str(resource_path("specorde_logo.ico"))))
    canvas.after(500, lambda: canvas.iconbitmap(str(resource_path("specorde_logo.ico"))))
    canvas.after(600, lambda: canvas.iconphoto(True, logo))
except Exception:
    logging.exception("Icon failed to load")
check_messages()

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

pictures_button = ctk.CTkButton(left, text="Pictures", font=("Bahnschrift Light Condensed", 16), command=pictures_open)
pictures_button.grid(sticky="nw", pady=18, padx=18)

settings_button = ctk.CTkButton(left, text="Settings", font=("Bahnschrift Light Condensed", 16), command=settings_open)
settings_button.grid(sticky="nw", pady=18, padx=18)

tutorial_button = ctk.CTkButton(left, text="Tutorial", font=("Bahnschrift Light Condensed", 16), command=tutorial_open)
tutorial_button.grid(sticky="nw", pady=18, padx=18)
left_footer = ctk.CTkLabel(left, text=f"© 2026 Richard Vajko", text_color="grey", font=("Bahnschrift Light Condensed", 11), justify="left")
left_footer.grid(row=10, column=0, sticky="sw", pady=2, padx=10)

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

#pictures
overview_frame = ctk.CTkScrollableFrame(middle, width=664, height=648, fg_color="#20222e")
culling_frame = ctk.CTkScrollableFrame(middle, width=664, height=648, fg_color="#20222e")
pictures_label = ctk.CTkLabel(header, text="Pictures", font=("Bahnschrift Light Condensed", 32))
pictures_overview = ctk.CTkButton(header, command=lambda: pictures_change(0), text="Overview", font=("Bahnschrift Light Condensed", 13), width=112, height=14)
pictures_culling = ctk.CTkButton(header, command=lambda: pictures_change(1), text="Culling", font=("Bahnschrift Light Condensed", 13), width=112, height=14)
pictures_size_label = ctk.CTkLabel(header, text="Density: ", font=("Bahnschrift Light Condensed", 13))
pictures_size_changer = ctk.CTkButton(header, command=pictures_size, text="Middle", font=("Bahnschrift Light Condensed", 13), width=77, height=14)

#tutorial
tutorial_label = ctk.CTkLabel(header, text="Tutorial", font=("Bahnschrift Light Condensed", 30))
tutorial_frame = ctk.CTkFrame(middle, fg_color="transparent")
tutorial_frame.grid_columnconfigure(0, weight=1)
 
tutorial_intro_title = ctk.CTkLabel(tutorial_frame, text="Welcome to Specorde", font=("Bahnschrift Light Condensed", 22))
tutorial_intro_text = ctk.CTkLabel(tutorial_frame, text="Pick a folder, tick what you want done and press Execute. Your progress shows in the Activity panel on the right", font=("Bahnschrift Light Condensed", 16), wraplength=480, justify="left", anchor="w")
 
tutorial_functions_title = ctk.CTkLabel(tutorial_frame, text="Functions", font=("Bahnschrift Light Condensed", 21))
 
tutorial_find_title = ctk.CTkLabel(tutorial_frame, text="Find duplicates", font=("Bahnschrift Light Condensed", 18))
tutorial_find_text = ctk.CTkLabel(tutorial_frame, text="Finds identical files. In Settings, choose if they're moved to a 'duplicates' folder or sent to the recycle bin", text_color="grey", font=("Bahnschrift Light Condensed", 15), wraplength=480, justify="left", anchor="w")
tutorial_sort_title = ctk.CTkLabel(tutorial_frame, text="Sort files", font=("Bahnschrift Light Condensed", 18))
tutorial_sort_text = ctk.CTkLabel(tutorial_frame, text="Moves files into a 'sorted' folder by date. Choose date taken or date modified, and year/month or year/month/day", text_color="grey", font=("Bahnschrift Light Condensed", 15), wraplength=480, justify="left", anchor="w")
tutorial_rename_title = ctk.CTkLabel(tutorial_frame, text="Rename files", font=("Bahnschrift Light Condensed", 18))
tutorial_rename_text = ctk.CTkLabel(tutorial_frame, text="Gives your files new numbered names. Choose the original name, a date or your own name (up to 16 letters, numbers or underscores)", text_color="grey", font=("Bahnschrift Light Condensed", 15), wraplength=480, justify="left", anchor="w")
 
tutorial_howto_title = ctk.CTkLabel(tutorial_frame, text="How to use it", font=("Bahnschrift Light Condensed", 21))
tutorial_howto_text = ctk.CTkLabel(tutorial_frame, text="1.  Press 'Choose a folder' and pick the folder to tidy.\n2.  Adjust the functions in 'Settings' (optional).\n3.  Tick what you want in 'Organize'.\n4.  Press 'Execute' and wait for the status to finish.\n5.  'Preview' shows what would happen without changing files. 'Restore folder' undoes the last run", font=("Bahnschrift Light Condensed", 16), wraplength=480, justify="left", anchor="w")
 
tutorial_intro_title.grid(row=0, column=0, padx=6, pady=(0,4), sticky="w")
tutorial_intro_text.grid(row=1, column=0, padx=(8,6), pady=(0,14), sticky="w")
tutorial_functions_title.grid(row=2, column=0, padx=(6,6), pady=(0,6), sticky="w")
tutorial_find_title.grid(row=3, column=0, padx=(10,6), sticky="w")
tutorial_find_text.grid(row=4, column=0, padx=(12,6), pady=(0,8), sticky="w")
tutorial_sort_title.grid(row=5, column=0, padx=(10,6), sticky="w")
tutorial_sort_text.grid(row=6, column=0, padx=(12,6), pady=(0,8), sticky="w")
tutorial_rename_title.grid(row=7, column=0, padx=(10,6), sticky="w")
tutorial_rename_text.grid(row=8, column=0, padx=(12,6), pady=(0,14), sticky="w")
tutorial_howto_title.grid(row=9, column=0, padx=(6,6), pady=(0,6), sticky="w")
tutorial_howto_text.grid(row=10, column=0, padx=(14,6), sticky="w")

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
            check_text.configure(text=f"Your custom name is:  ' {text} '")
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
custom_check_icon = ctk.CTkLabel(rename_settings, text="!", font=("Bahnschrift Light Condensed", 26), fg_color="#1c1c24", width=32, corner_radius=8)

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
        q.put(("status", "Preview mode on"))
        logging.info("Preview (dry run) turned on")
    else:
        dry_run = 0
        execute_button.configure(text="Execute", text_color="white")
        q.put(("status", "Preview mode off"))
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
file_disclaimer = ctk.CTkLabel(footer, text="DISCLAIMER: Files that exist only in the cloud are skipped! RAW files are sorted by date modified!", text_color="grey",  font=("Bahnschrift Light Condensed", 11))
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
        logging.exception("Log window icon failed")

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
        messagebox.showinfo("Specorde", "No log file has been created yet")
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
        logging.exception("Could not show log")
        close_log()
        messagebox.showwarning("Specorde", f"Could not show the log.\n\n({e})")
#version
version_frame = ctk.CTkFrame(right, fg_color="transparent")
version_label = ctk.CTkLabel(version_frame, text=f"v{app_version}", text_color="grey", font=("Bahnschrift Light Condensed", 10))
log_button = ctk.CTkButton(version_frame, text="Open log", font=("Bahnschrift Light Condensed", 12), command=open_log, width=52, height=24)
version_frame.grid(row=11, column=0, sticky="sw", padx=14, pady=(0,10))
version_label.grid(row=0, column=0, sticky="w")
log_button.grid(row=0, column=2, padx=(152,24), sticky="e")

canvas.mainloop()