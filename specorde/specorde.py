 #This is my attempt at making an actually sellable product.
#Not even 2 weeks into python at this point
#Start - Sunday, 27th Sep. 2026

from datetime import datetime
from pathlib import Path
import hashlib
import os
import sys
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ExifTags
import json
import threading
import logging
import queue
from send2trash import send2trash
import ctypes

#version
app_version = "1.0.0.1"

#Developer settings
month_dict = {
    1: "(1) January", 2: "(2) February", 3: "(3) March", 4: "(4) April", 5: "(5) May", 6: "(6) June", 7: "(7) July", 8: "(8) August", 9: "(9) September", 10: "(10) October", 11: "(11) November", 12: "(12) December"
}
years_used = []
suffix = [
    "(1)", "(2)", "(3)", "(4)", "(5)", "(6)", "(7)", "(8)", "(9)", "(10)", "(11)", "(12)", "(13)", "(14)", "(15)", "(16)", "(17)", "(18)", "(19)", "(20)", "- Copy"
]
q = queue.Queue()
cfg = {}
check = 1
path = Path(os.getenv("APPDATA")) / "Specorde"
path.mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=path / "specorde.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.info("Specorde started")
memory = path / "memory.json"
journal_path = path / "journals"
journal_name = None
size = 0
dry_run = 0

try:
    with open(memory, "r") as f:
        tutorial_seen = json.load(f)
except FileNotFoundError:
    logging.info("File not found, building a new one...")
    memory = Path(memory)
    memory.touch(exist_ok=True)
    with open(memory, "w") as f:
        json.dump(0, f)
    tutorial_seen = 0
except json.JSONDecodeError:
    logging.warning("memory.json was empty, starting fresh")
    memory = Path(memory)
    memory.touch(exist_ok=True)
    with open(memory, "w") as f:
        json.dump(0, f)
    tutorial_seen = 0

if tutorial_seen == 0:
    currently_open = 1
else:
    currently_open = 0  

exif_suffix = {".jpg", ".jpeg", ".tiff", ".tif", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2"}
#Script itself
def start_execute(task):
    threading.Thread(target=task, daemon=True).start()

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
    if actions_rename.get() and settings_rename_pattern.get() == "custom name + number" and check == 0:
        messagebox.showwarning("Specorde", "Your custom name is not valid. Check it in Settings.")
        return
    if not target_folder.is_dir():
        messagebox.showwarning("Specorde", "That folder no longer exists. Please choose it again.")
        return
    count = sum(1 for f in target_folder.iterdir() if f.is_file() and not is_protected_item(f))
    message = f"This will change files in '{target_folder.name}' ({count} files)."
    if actions_find.get() and settings_duplicate_delete.get() == "Deleted":
        message += "\n\nDuplicates will be sent to the Recycle Bin. On USB or network drives they may be deleted permanently."
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
    q.put(("lock", None))
    start_execute(execute)
reset_job = None
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
                bar.grid(row=3, padx=25, sticky="w", pady=(8,2))
            elif kind == "bar_text_show":
                bar_text.grid(row=4, padx=32, sticky="w")
            elif kind == "bar_hide":
                bar.grid_forget()
            elif kind == "bar_text_hide":
                bar_text.grid_forget()
            elif kind == "status_reset":
                if reset_job is not None:
                    canvas.after_cancel(reset_job)
                reset_job = canvas.after(1700, lambda: status.configure(text="Sitting..."))
            elif kind == "lock":
                execute_button.configure(fg_color="#173348", state="disabled")
                folder_browser.configure(fg_color="#173348", state="disabled")
            elif kind == "unlock":
                execute_button.configure(fg_color="#1f6aa5", state="normal")
                folder_browser.configure(fg_color="#1f6aa5", state="normal")
            elif kind == "folder_reset":
                folder_browser.configure(text="Choose a new folder")
                folder_chosen.configure(text="Folder chosen:")
    except queue.Empty:
        pass
    canvas.after(20, check_messages)

def parse_exif_date(text):
    try:
        return datetime.strptime(text, "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None

def safe_rename(item, destination):
    try:
        item.rename(destination)
        note = {"from": str(item), "to": str(destination)}
        with open(journal_name, "a") as f:
            f.write(json.dumps(note) + "\n")
    except OSError:
        logging.exception("Could not move or rename %s", item.name)

def find_last_run():
    try:
        for file in sorted(journal_path.glob("run_*.jsonl"), reverse=True):
            with open(file) as f:
                header = json.loads(f.readline())
            if header.get("folder") == str(target_folder):
                return file
        return None #display message here if folder not restorable
    except FileNotFoundError:
        pass
    except PermissionError:
        pass

def get_exif(path):
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if exif:
                date_str = None
                try:
                    date_str = exif.get_ifd(0x8769).get(36867)
                except Exception:
                    pass
                date_str = date_str or exif.get(36867) or exif.get(306)
                if not date_str:
                    try:
                        exif_ifd = exif.get_ifd(0x8769)
                        date_str = exif_ifd.get(36867) or exif_ifd.get(306)
                    except Exception:
                        pass
                if date_str:
                    if isinstance(date_str, bytes):
                        return date_str.decode('utf-8', errors='ignore').strip()
                    return str(date_str).strip()
    except Exception:
        pass
    return None


def sort():
    global bar_text
    global status
    global bar
    try:
        done = 0
        q.put(("bar_set", 0))
        for item in list(target_folder.iterdir()):
            q.put(("bar_show", None))
            q.put(("bar_text_show", None))

            try:
                if item.is_file() and not is_protected_item(item):
                    done = done + item.stat().st_size / (1024*1024*1024)

                    if cfg["sortby"] == "Date modified":
                        file_time = datetime.fromtimestamp(item.stat().st_mtime)
                        year = str(file_time.year)
                        month = month_dict[file_time.month]
                        day = str(file_time.day)
                    elif cfg["sortby"] == "Date taken":

                        if item.suffix.lower() not in exif_suffix:
                            file_time = datetime.fromtimestamp(item.stat().st_mtime)
                            year = str(file_time.year)
                            month = month_dict[file_time.month]
                            day = str(file_time.day)
                            logging.debug("%s has an unsupported suffix, using date modified", item.name)
                        else:
                            exif_string = get_exif(item)
                            photo_date = parse_exif_date(exif_string) if exif_string else None
                            if photo_date:
                                year = str(photo_date.year)
                                month = month_dict[photo_date.month]
                                day = str(photo_date.day)
                            else:
                                file_time = datetime.fromtimestamp(item.stat().st_mtime)
                                year = str(file_time.year)
                                month = month_dict[file_time.month]
                                day = str(file_time.day)
                                logging.warning(f"No date taken for {item.name}, sorted by date modified instead")

                    sorted_dir.mkdir(exist_ok=True)
                    year_dir = sorted_dir / year
                    year_dir.mkdir(exist_ok=True)
                    month_dir = year_dir / month
                    month_dir.mkdir(exist_ok=True)
                    years_used.append(year)

                    if cfg["structure"] == "year/month":
                        destination = Path(month_dir/item.name)

                        if destination.exists():
                            counter = 1
                            while destination.exists():
                                destination = Path(month_dir/f"{item.stem}_{counter}{item.suffix}")
                                counter += 1
                        safe_rename(item, destination)

                    elif cfg["structure"] == "year/month/day":
                        day_dir = month_dir / day
                        day_dir.mkdir(exist_ok=True)
                        destination = Path(day_dir/item.name)

                        if destination.exists():
                            counter = 1
                            while destination.exists():
                                destination = Path(day_dir/f"{item.stem}_{counter}{item.suffix}")
                                counter += 1
                        safe_rename(item, destination)

                    try:
                        percent = done / folder_size * 100
                        if percent > 80:
                            q.put(("status", "Almost there!"))
                        else:
                            q.put(("status", "Sorting..."))
                        q.put(("bar_text", f"{percent :.2f}%"))
                        q.put(("bar_set", percent/100))

                    except ZeroDivisionError:
                        ()
            except Exception:
                logging.exception("Could not sort %s", item.name)

        q.put(("bar_text", "100%"))
        q.put(("status", "Files sorted!"))
        q.put(("bar_text_destroy", None))
        q.put(("bar_destroy", None))
        logging.info("Files sorted.")
    except NameError:
        q.put(("bar_text_destroy", None))
        q.put(("bar_destroy", None))
        q.put(("status", "You must pick a folder."))
        q.put(("status_reset", None))
    except FileNotFoundError:
        logging.exception("File not found")
        q.put(("bar_text_destroy", None))
        q.put(("bar_destroy", None))
    q.put(("status_reset", None))

def is_copy(file):
    return any(suf in file.stem for suf in suffix)

def remove_duplicate(file, mode):
    if mode == "Moved to a folder":
        destination = duplicates / file.name
        counter = 1
        while destination.exists():
            destination = duplicates / f"{file.stem}_{counter}{file.suffix}"
            counter += 1
        file.rename(destination)
    elif mode == "Deleted":
        send2trash(str(file))

def duplicate_finder():
    global bar_text
    global status
    global bar
    try:
        changed =0
        seen = {}
        size = 0
        mode = cfg["duplicate_mode"]
        q.put(("bar_set", 0))
        for item in list(target_folder.iterdir()):
            q.put(("bar_show", None))
            q.put(("bar_text_show", None))
            if item.is_file() and not is_protected_item(item):
                try:
                    if item.stat().st_size == 0:
                        continue
                    hash = get_hash(item)
                except OSError:
                    logging.exception("Could not read %s", item.name)
                    continue
                try:
                    size = size + item.stat().st_size / (1024*1024*1024)
                except FileNotFoundError:
                    logging.warning(f"File {item.name} not found")

                if hash in seen:
                    if mode == "Moved to a folder":
                        duplicates.mkdir(exist_ok=True)
                    try:
                        if is_copy(seen[hash]) and not is_copy(item):
                            remove_duplicate(seen[hash], mode)
                            seen[hash] = item
                        else:
                            remove_duplicate(item, mode)
                        changed = 1
                    except Exception:
                        logging.exception("Could not remove duplicate %s", item.name)
                else:
                    seen[hash] = item

                try:
                    percent = size / folder_size * 100
                    if percent > 80:
                        q.put(("status", "Almost there!"))
                    else:
                        q.put(("status", "Finding duplicates"))
                    q.put(("bar_text", f"{percent :.2f}%"))
                    q.put(("bar_set", percent/100))
                except ZeroDivisionError:
                    ()
            else:
                try:
                    size = size + sum(f.stat().st_size for f in item.rglob("*")) / (1024*1024*1024)
                except FileNotFoundError:
                    logging.warning(f"File {item.name} not found")
        if mode == "Moved to a folder":
            if not duplicates.exists():
                q.put(("bar_text", "100%"))
                q.put(("status", "No duplicates found!"))
            elif not any(duplicates.iterdir()):
                q.put(("bar_text", "100%"))
                q.put(("status", "No duplicates found!"))    
            elif duplicates.exists():
                if changed == 0:
                    q.put(("bar_text", "100%"))
                    q.put(("status", "No new duplicates!"))
                elif changed == 1:
                    q.put(("bar_text", "100%"))
                    q.put(("status", "All duplicates found!"))
        elif mode == "Deleted":
            if changed == 0:
                q.put(("bar_text", "100%"))
                q.put(("status", "No duplicates found!"))
            elif changed == 1:
                q.put(("bar_text", "100%"))
                q.put(("status", "Duplicates removed!"))
        q.put(("bar_text_destroy", None))
        q.put(("bar_destroy", None))
    except NameError:
        q.put(("bar_text_destroy", None))
        q.put(("bar_destroy", None))
        q.put(("status", "You must pick a folder."))
    except FileNotFoundError:
        logging.exception("Duplicate finder: file not found")
        q.put(("bar_text_destroy", None))
        q.put(("bar_destroy", None))
    except PermissionError:
        logging.exception("Duplicate finder: permission denied")
    q.put(("status_reset", None))

def watermark():
    try:
        ()
    except NameError:
        q.put(("status", "You must pick a folder."))

def rename():
    global bar
    global bar_text
    global status
    if check == 0:
        q.put(("status", "Your custom name is not valid."))
        q.put(("status_reset", None))
        return
    q.put(("bar_set", 0))
    q.put(("bar_show", None))
    q.put(("bar_text_show", None))
    size = 0
    choice = cfg["pattern"]
    renameby = cfg["renameby"]
    custom = cfg["custom"]
    number = 0
    try:
        files = [f for f in target_folder.iterdir() if f.is_file() and not is_protected_item(f)]
        count = len(files)
        width = len(str(count))
        for item in files:
            counter = 0
            if item.is_file():
                try:
                    size = size + item.stat().st_size / (1024*1024*1024)
                except FileNotFoundError:
                    logging.warning(f"File {item.name} not found")
                number += 1
                number_text = str(number).zfill(width)

                try:
                    percent = size / folder_size * 100
                    if percent > 80:
                        q.put(("status", "Almost there!"))
                    else:
                        q.put(("status", "Renaming the files"))
                    q.put(("bar_text", f"{percent :.2f}%"))
                    q.put(("bar_set", percent/100))
                except ZeroDivisionError:
                    ()
                                    
                if choice == "date + number":
                    if renameby == "Date modified":
                        file_time = datetime.fromtimestamp(item.stat().st_mtime)
                        year = str(file_time.year)
                        month = str(file_time.month).zfill(2)
                        day = str(file_time.day).zfill(2)

                        destination = Path(f"{target_folder}/{year}-{month}-{day}_{number_text}{item.suffix}")
                        if destination.exists():
                            while destination.exists():
                                counter += 1
                                destination = Path(f"{target_folder}/{year}-{month}-{day}_{number_text}_{counter}{item.suffix}")
                        safe_rename(item, destination)

                    elif renameby == "Date taken":
                        if item.suffix.lower() not in exif_suffix:
                            file_time = datetime.fromtimestamp(item.stat().st_mtime)
                            year = str(file_time.year)
                            month = str(file_time.month).zfill(2)
                            day = str(file_time.day).zfill(2)
                            logging.debug("%s has an unsupported suffix, using date modified", item.name)
                        else:
                            exif_string = get_exif(item)
                            photo_date = parse_exif_date(exif_string) if exif_string else None
                            if photo_date:
                                year = str(photo_date.year)
                                month = str(photo_date.month).zfill(2)
                                day = str(photo_date.day).zfill(2)
                            else:
                                file_time = datetime.fromtimestamp(item.stat().st_mtime)
                                year = str(file_time.year)
                                month = str(file_time.month).zfill(2)
                                day = str(file_time.day).zfill(2)
                                logging.warning(f"No date taken for {item.name}, renamed by date modified instead")

                        destination = Path(f"{target_folder}/{year}-{month}-{day}_{number_text}{item.suffix}")
                        if destination.exists():
                            while destination.exists():
                                counter += 1
                                destination = Path(f"{target_folder}/{year}-{month}-{day}_{number_text}_{counter}{item.suffix}")
                        safe_rename(item, destination)
                elif choice == "original name + number":
                    destination = Path(f"{target_folder}/{item.stem}_{number_text}{item.suffix}")
                    if destination.exists():
                        while destination.exists():
                            counter += 1
                            destination = Path(f"{target_folder}/{item.stem}_{number_text}_{counter}{item.suffix}")
                    safe_rename(item, destination)

                elif choice == "custom name + number":
                    destination = Path(f"{target_folder}/{custom}_{number_text}{item.suffix}")
                    if destination.exists():
                        while destination.exists():
                            counter += 1
                            destination = Path(f"{target_folder}/{custom}_{number_text}_{counter}{item.suffix}")
                    safe_rename(item, destination)
                
            else:
                try:
                    size = size + sum(f.stat().st_size for f in item.rglob("*")) / (1024*1024*1024)
                except FileNotFoundError:
                    logging.warning(f"File {item.name} not found")
        q.put(("bar_text", "100%"))
        q.put(("status", "Files renamed!"))
        q.put(("bar_text_destroy", None))
        q.put(("bar_destroy", None))
        logging.info("Files renamed.")
    except NameError:
        q.put(("bar_text_destroy", None))
        q.put(("bar_destroy", None))
        q.put(("status", "You must pick a folder."))
        q.put(("status_reset", None))
    except FileNotFoundError:
        logging.exception("File not found")
        q.put(("bar_text_destroy", None))
        q.put(("bar_destroy", None))
    q.put(("status_reset", None))

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
    except (AttributeError, OSError):
        pass
    return False

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

def measure_folder(folder):
    global folder_size
    total = 0
    try:
        for f in folder.rglob("*"):
            if f not in ["sorted_specorde", "duplicates_specorde"]:
                try:
                    total += f.stat().st_size
                except OSError:
                    pass
    except Exception:
        logging.exception("Could not measure %s", folder.name)
    folder_size = total / (1024*1024*1024)
    q.put(("status", "Folder ready!"))
    q.put(("status_reset", None))
    q.put(("unlock", None))

def pick_folder():
    global target_folder
    global folder_size
    global duplicates
    global sorted_dir

    chosen = filedialog.askdirectory()
    if not chosen:
        return
    if is_dangerous(Path(chosen)):
        messagebox.showwarning("Specorde", "This folder is protected and can't be organized. Please pick another folder.")
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
    folder_size = 0
    q.put(("lock", None))
    q.put(("status", "Reading folder..."))
    threading.Thread(target=measure_folder, args=(target_folder,), daemon=True).start()

allowed_characters = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z", "_", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
def get_hash(filepath:  Path):
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def execute():
    global journal_name
    journal_path.mkdir(exist_ok=True)
    try:
        if dry_run == 0:
            logging.info("Run started on '%s'", target_folder.name)

            if cfg["sort"] or cfg["rename"]:
                journal_name = journal_path / f"run_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.jsonl"
                with open(journal_name, "w") as f:
                    f.write(json.dumps({"folder": str(target_folder)}) + "\n")
 
            if cfg["find"]:
                logging.info("Finding duplicates (%s)...", cfg["duplicate_mode"])
                duplicate_finder()
            if cfg["rename"]:
                rename_detail = cfg["pattern"]
                if rename_detail == "date + number":
                    rename_detail = f"{rename_detail}, by {cfg['renameby']}"
                elif rename_detail == "custom name + number":
                    rename_detail = f"{rename_detail}, name '{cfg['custom']}'"
                logging.info("Renaming files (%s)...", rename_detail)
                rename()
            if cfg["sort"]:
                logging.info("Sorting (by %s, structure %s)...", cfg["sortby"], cfg["structure"])
                sort()
            q.put(("unlock", None))
        elif dry_run == 1:
            q.put(("status", "Check log."))
            if cfg["find"]:
                logging.info("Finding duplicates (%s)...", cfg["duplicate_mode"])
            if cfg["rename"]:
                rename_detail = cfg["pattern"]
                if rename_detail == "date + number":
                    rename_detail = f"{rename_detail}, by {cfg['renameby']}"
                elif rename_detail == "custom name + number":
                    rename_detail = f"{rename_detail}, name '{cfg['custom']}'"
                logging.info("Renaming files (%s)...", rename_detail)
            if cfg["sort"]:
                logging.info("Sorting (by %s, structure %s)...", cfg["sortby"], cfg["structure"])
            q.put(("unlock", None))
            q.put(("status_reset", None))
    except Exception:
        logging.exception("Error trying to execute")
        q.put(("bar_text_destroy", None))
        q.put(("bar_destroy", None))
        q.put(("status", "Something went wrong. See log."))
        q.put(("status_reset", None))
        q.put(("unlock", None))

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
                    moved = 1
                except OSError:
                    logging.error("Could not restore %s", item.name)
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
                        moved = 1
                    except OSError:
                        logging.error("Could not restore %s", month_sub.name)
                else:
                    for item in list(month_sub.iterdir()):
                        counter = 0
                        destination = dest/item.name
                        while destination.exists():
                            counter += 1
                            destination = Path(f"{dest}/{item.stem}_restored_{counter}{item.suffix}")
                        try:
                            item.rename(destination)
                            moved = 1
                        except OSError:
                            logging.error("Could not restore %s", item.name)
                    try:
                        month_sub.rmdir()
                    except OSError:
                        ()
            try:
                month.rmdir()
            except OSError:
                ()
        try:
            year.rmdir()
        except OSError:
            ()
    return moved

def restore_from_journal(entries):
        moved = 0
        moved_sort = 0
        for entry in reversed(entries):
            moved_to = Path(entry["to"])
            original = Path(entry["from"])

            if moved_to.exists():
                try:
                    counter = 0
                    destination = original
                    while destination.exists():
                        counter += 1
                        destination = Path(f"{original.parent}/{original.stem}_restored_{counter}{original.suffix}")
                    moved_to.rename(destination)
                    moved = 1
                except OSError:
                    logging.exception("Could not restore %s", moved_to.name)
        if sorted_dir.exists():
            moved_sort = restore_sorted(sorted_dir, target_folder)
            try:
                sorted_dir.rmdir()
            except OSError:
                ()
        if moved_sort:
            moved = 1
        return moved

def start_restoring():
    global target_folder
    entries = []
    moved = 0
    counter = 0
    targed_folder_remove = 0
    if "target_folder" not in globals():
        q.put(("status", "You must pick a folder."))
        q.put(("status_reset", None))
        return
    
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
        with open(journal_file) as f:
            f.readline()
            for line in f:
                try:
                    item = json.loads(line)
                    entries.append(item)
                except json.JSONDecodeError:
                    continue

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
        duplicates_moved = restore_duplicates(duplicates, target_folder)
        try:
            duplicates.rmdir()
        except OSError:
            ()
        if moved or duplicates_moved:
            q.put(("status", "Everything back in its place!"))
        else:
            q.put(("status", "Nothing to restore..."))
        q.put(("status_reset", None))

    if moved and journal_file is not None:
        try:
            journal_file.rename(journal_file.with_suffix(".used"))
        except OSError:
            ()

    if targed_folder_remove == 1:
        try:
            target_folder.rmdir()
            del target_folder
            q.put(("folder_reset", None))
        except OSError:
            ()





def middle_reset():
    global header
    try:
        for widget in header.winfo_children():
            widget.grid_forget()
    except Exception:
        pass
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
tutorial_intro_text = ctk.CTkLabel(tutorial_frame, text="Pick a folder, tick what you want done and press Execute. Your progress shows in the Activity panel on the right.", font=("Bahnschrift Light Condensed", 16), wraplength=480, justify="left", anchor="w")
 
tutorial_functions_title = ctk.CTkLabel(tutorial_frame, text="Functions", font=("Bahnschrift Light Condensed", 21))
 
tutorial_find_title = ctk.CTkLabel(tutorial_frame, text="Find duplicates", font=("Bahnschrift Light Condensed", 18))
tutorial_find_text = ctk.CTkLabel(tutorial_frame, text="Finds identical files. In Settings, choose if they're moved to a 'duplicates' folder or sent to the recycle bin.", text_color="grey", font=("Bahnschrift Light Condensed", 15), wraplength=480, justify="left", anchor="w")
tutorial_sort_title = ctk.CTkLabel(tutorial_frame, text="Sort files", font=("Bahnschrift Light Condensed", 18))
tutorial_sort_text = ctk.CTkLabel(tutorial_frame, text="Moves files into a 'sorted' folder by date. Choose date taken or date modified, and year/month or year/month/day.", text_color="grey", font=("Bahnschrift Light Condensed", 15), wraplength=480, justify="left", anchor="w")
tutorial_rename_title = ctk.CTkLabel(tutorial_frame, text="Rename files", font=("Bahnschrift Light Condensed", 18))
tutorial_rename_text = ctk.CTkLabel(tutorial_frame, text="Gives your files new numbered names. Choose the original name, a date or your own name (up to 16 letters, numbers or underscores).", text_color="grey", font=("Bahnschrift Light Condensed", 15), wraplength=480, justify="left", anchor="w")
 
tutorial_howto_title = ctk.CTkLabel(tutorial_frame, text="How to use it", font=("Bahnschrift Light Condensed", 21))
tutorial_howto_text = ctk.CTkLabel(tutorial_frame, text="1.  Press 'Choose a folder' and pick the folder to tidy.\n2.  Adjust the functions in 'Settings' (optional).\n3.  Tick what you want in 'Organize'.\n4.  Press 'Execute' and wait for the status to finish.", font=("Bahnschrift Light Condensed", 16), wraplength=480, justify="left", anchor="w")
 
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
            if char == " ":
                check_text.configure(text=f"Your custom name can't have a space!")
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
    global execute_button
    if dry_run == 0:
        dry_run = 1
        execute_button.configure(text_color="#1f2029")
        q.put(("status", "Dry run turned on."))
        logging.info("Dry run turned off.")
    else:
        dry_run = 0
        execute_button.configure(text_color="white")
        q.put(("status", "Dry run turned off."))
        logging.info("Dry run turned off.")
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
file_disclaimer = ctk.CTkLabel(footer, text="DISCLAIMER: Files that exist only in the cloud are skipped!", text_color="grey",  font=("Bahnschrift Light Condensed", 11))
restore_button = ctk.CTkButton(footer, text="Restore folder", font=("Bahnschrift Light Condensed", 11), command=lambda: start_execute(start_restoring), width=76, height=24)
dry_run_button = ctk.CTkButton(footer, text="Dry run", font=("Bahnschrift Light Condensed", 11), command=dry_run_toggle, width=52, height=24)

#show tutorial
if tutorial_seen == 0:
    tutorial_open()
    tutorial_seen = 1
    try:
        with open(memory, "w") as f:
            json.dump(tutorial_seen, f)
    except FileNotFoundError:
        logging.exception("File not found")
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
bar = ctk.CTkProgressBar(right)
q.put(("bar_hide", None))
bar_text = ctk.CTkLabel(right, text="")
q.put(("bar_text_hide", None))

log_window = None

def close_log():
    global log_window
    if log_window is not None:
        try:
            log_window.destroy()
        except Exception:
            pass
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