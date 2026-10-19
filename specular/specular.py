 #This is my attempt at making an actually sellable product.
#Not even 2 weeks into python at this point
#Start - Sunday, 27th Sep. 2026

from datetime import datetime
from pathlib import Path
import hashlib
import customtkinter as ctk
from tkinter import filedialog
from PIL import Image, ImageTk, ExifTags
import json
import threading
import queue

#Developer settings
month_dict = {
    1: "(1) January", 2: "(2) February", 3: "(3) March", 4: "(4) April", 5: "(5) May", 6: "(6) June", 7: "(7) July", 8: "(8) August", 9: "(9) September", 10: "(10) October", 11: "(11) November", 12: "(12) December"
}
years_used = []
suffix = [
    "(1)", "(2)", "(3)", "(4)", "(5)", "(6)", "(7)", "(8)", "(9)", "(10)", "- copy", "- Copy"
]
q = queue.Queue()


try:
    with open("memory.json", "r") as f:
        tutorial_seen = json.load(f)

except FileNotFoundError:
    print("File not found.")
    memory = Path("memory.json")
    memory.touch(exist_ok=True)
    with open("memory.json", "w") as f:
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
    start_execute(execute)

def check_messages():
    try:
        while True:
            kind, value = q.get_nowait()
            if kind == "status":
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
                status.after(1700, lambda: status.configure(text="Sitting..."))
            canvas.update_idletasks()
    except queue.Empty:
        pass
    canvas.after(20, check_messages)

def get_exif(path):
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if exif:
                date_str = exif.get(36867) or exif.get(306)
                
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

        q.put(("bar_set", 0))
        for item in target_folder.iterdir():
            q.put(("bar_show", None))
            q.put(("bar_text_show", None))

            try:
                if item.is_file() or item.is_dir() and item.name not in ["duplicates", "sorted"]:
                    if settings_sort_sortby.get() == "Date modified":
                        file_time = datetime.fromtimestamp(item.stat().st_mtime)
                        year = str(file_time.year)
                        month = month_dict[file_time.month]
                        day = str(file_time.day)
                    elif settings_sort_sortby.get() == "Date taken":

                        if item.suffix.lower() not in exif_suffix:
                            file_time = datetime.fromtimestamp(item.stat().st_mtime)
                            year = str(file_time.year)
                            month = month_dict[file_time.month]
                            day = str(file_time.day)
                            print(f"{item.name} has an unsupported suffix. sorting by date modified")
                        else:
                            exif_string = get_exif(item)
                            if exif_string:
                                photo_date = datetime.strptime(exif_string, "%Y:%m:%d %H:%M:%S")
                                year = str(photo_date.year)
                                month = month_dict[photo_date.month]
                                day = str(photo_date.day)
                                print(f"1 - Sorted item {item.name} by date taken.")
                            else:
                                file_time = datetime.fromtimestamp(item.stat().st_mtime)
                                year = str(file_time.year)
                                month = month_dict[file_time.month]
                                day = str(file_time.day)
                                print(f"0 - Couldn't sort item {item.name} by date taken, sorted by date modified instead.")

                    sorted_dir.mkdir(exist_ok=True)
                    year_dir = sorted_dir / year
                    year_dir.mkdir(exist_ok=True)
                    month_dir = year_dir / month
                    month_dir.mkdir(exist_ok=True)
                    years_used.append(year)

                    if settings_sort_structure.get() == "year/month":
                        destination = Path(month_dir/item.name)

                        if destination.exists():
                            counter = 1
                            while destination.exists():
                                destination = Path(month_dir/f"{item.stem}_{counter}{item.suffix}")
                                counter += 1
                        item.rename(destination)

                    elif settings_sort_structure.get() == "year/month/day":
                        day_dir = month_dir / day
                        day_dir.mkdir(exist_ok=True)
                        destination = Path(day_dir/item.name)

                        if destination.exists():
                            counter = 1
                            while destination.exists():
                                destination = Path(day_dir/f"{item.stem}_{counter}{item.suffix}")
                                counter += 1
                        item.rename(destination)
                    try:
                        percent = sum(f.stat().st_size for f in sorted_dir.rglob('*') if f.is_file())/(1024*1024*1024) / folder_size * 100
                        if percent > 80:
                            q.put(("status", "Almost there!"))
                        else:
                            q.put(("status", "Sorting..."))
                        q.put(("bar_text", f"{percent :.2f}%"))
                        q.put(("bar_set", percent/100))

                    except ZeroDivisionError:
                        ()
            except PermissionError:
                print(f"Not permitted to move {item.name}.")


        q.put(("bar_text", "100%"))
        q.put(("status", "Files sorted!"))
        q.put(("bar_text_destroy", None))
        q.put(("bar_destroy", None))
        print("Files sorted.")
    except NameError:
        print("You must pick a folder.")
        q.put(("bar_text_destroy", None))
        q.put(("bar_destroy", None))
        q.put(("status", "You must pick a folder."))
        q.put(("status_reset", None))
    except FileNotFoundError:
        print("File not found.")
        q.put(("bar_text_destroy", None))
        q.put(("bar_destroy", None))
    q.put(("status_reset", None))
    
def restore_sort():
    global bar_text
    global status
    global bar
    try:
        if target_folder.name == "sorted":
            q.put(("status", "Restoring sorted files..."))
            for year in target_folder.iterdir():
                for month in year.iterdir():
                    for file in month.iterdir():
                        file.rename(target_folder.parent/file.name)
                    month.rmdir()
                year.rmdir()
            target_folder.rmdir()
            status.after(500)
            q.put(("status", "Everything back in its place!"))
            q.put(("status_reset", None))
        elif not sorted_dir.exists():
            q.put(("status", "Nothing to restore."))
        else:
            q.put(("status", "Restoring sorted files...")) 
            for year in sorted_dir.iterdir():
                for month in year.iterdir():
                    for file in month.iterdir():
                        file.rename(target_folder/file.name)
                    month.rmdir()
                year.rmdir()
            sorted_dir.rmdir()
            status.after(500)
            q.put(("status", "Everything back in its place!"))
    
    except NameError:
        print("You must pick a folder.")
        q.put(("status", "You must pick a folder."))
    except FileNotFoundError:
        print("File not found.")
    except PermissionError:
        print("Not allowed to move this file.")
    q.put(("status_reset", None))

def duplicate_finder():
    global bar_text
    global status
    global bar
    try:
        changed =0
        seen = {}
        size = 0
        q.put(("bar_set", 0))
        for item in target_folder.iterdir():
            q.put(("bar_show", None))
            q.put(("bar_text_show", None))
            if item.is_file():
                hash = get_hash(item)
                try:
                    size = size + item.stat().st_size / (1024*1024*1024)
                except FileNotFoundError:
                    print(f"File {item.name} not found")

                if hash in seen:
                    if settings_duplicate_delete.get() == "Moved to a folder":
                        duplicates.mkdir(exist_ok=True)
                    if any(suf in seen[hash].stem for suf in suffix):
                        if any(suf in item.stem for suf in suffix):
                            if settings_duplicate_delete.get() == "Moved to a folder":
                                destination = Path(duplicates/item.name)

                                if destination.exists():
                                    counter = 1
                                    while destination.exists():
                                        destination = Path(duplicates/f"{item.stem}_{counter}{item.suffix}")
                                        counter += 1
                                item.rename(destination)
                            elif settings_duplicate_delete.get() == "Deleted":
                                item.unlink()
                            changed = 1
                        else:
                            if settings_duplicate_delete.get() == "Moved to a folder":
                                try:
                                    seen[hash].rename(duplicates/seen[hash].name)
                                except PermissionError:
                                    print(f"Permission error with {seen[hash]}")
                            elif settings_duplicate_delete.get() == "Deleted":
                                seen[hash].unlink()
                            changed = 1
                            seen[hash] = Path(item)
                else:
                    seen[hash] = Path(item)

                try:
                    percent = size / folder_size * 100
                    print(item.name, percent)
                    if percent > 80:
                        q.put(("status", "Almost there!"))
                    else:
                        q.put(("status", "Finding all the duplicates"))
                    q.put(("bar_text", f"{percent :.2f}%"))
                    q.put(("bar_set", percent/100))
                except ZeroDivisionError:
                    ()
            else:
                try:
                    size = size + sum(f.stat().st_size for f in item.rglob("*")) / (1024*1024*1024)
                except FileNotFoundError:
                    print(f"File {item.name} not found")
        if settings_duplicate_delete.get() == "Moved to a folder":
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
        elif settings_duplicate_delete.get() == "Deleted":
            if changed == 0:
                q.put(("bar_text", "100%"))
                q.put(("status", "No duplicates found!"))
            elif changed == 1:
                q.put(("bar_text", "100%"))
                q.put(("status", "All duplicates terminated!"))
        q.put(("bar_text_destroy", None))
        q.put(("bar_destroy", None))
    except NameError:
        print("Name Error")
        q.put(("bar_text_destroy", None))
        q.put(("bar_destroy", None))
        q.put(("status", "You must pick a folder."))
    except FileNotFoundError:
        print("File Not Found Error")
        q.put(("bar_text_destroy", None))
        q.put(("bar_destroy", None))
    except PermissionError:
        print("Permission Error Error")
    q.put(("status_reset", None))

def restore_duplicate():
    global status
    global bar_text
    global bar
    try:
        if target_folder.name == "duplicates":
            q.put(("status", "Restoring duplicates..."))
            for item in target_folder.iterdir():
                item.rename(target_folder.parent/item.name)
            target_folder.rmdir()
            status.after(500)
            q.put(("status", "Everything back in its place!"))
    
        elif not duplicates.exists():
            q.put(("status", "Nothing to restore."))
        else:
            q.put(("status", "Restoring duplicates..."))  
            for file in duplicates.iterdir():
                if file.is_file():
                    file.rename(target_folder/file.name)
            duplicates.rmdir()
            status.after(500)
            q.put(("status", "Everything back in its place!"))

    except NameError:
        print("You must pick a folder.")
        q.put(("status", "You must pick a folder."))
    except FileNotFoundError:
        print("File not found.")
    q.put(("status_reset", None))
def watermark():
    try:
        ()
    except NameError:
        print("You must pick a folder.")
        q.put(("status", "You must pick a folder."))

def rename():
    try:
        if settings_rename_pattern.get() == "date + number":
            ()
        elif settings_rename_pattern.get() == "original name + number":
            ()
        else:
            if len(settings_rename_custom.get('1.0', "end-1c")) > 12:
                ()
    except NameError:
        print("You must pick a folder.")
        q.put(("status", "You must pick a folder."))

def pick_folder():
    global target_folder
    global folder_size
    global duplicates
    global sorted_dir

    chosen = filedialog.askdirectory()

    while True:
        if chosen:
            target_folder = Path(chosen)
            folder_browser.configure(text = "Choose a different folder")
            folder_chosen.configure(text = f"Folder chosen: '{target_folder.name}'")
            break
        else:
            chosen = filedialog.askdirectory()

    folder_size = sum(f.stat().st_size for f in target_folder.rglob("*"))/(1024*1024*1024)
    sorted_dir = Path(target_folder/"sorted")
    duplicates = Path(target_folder/"duplicates")

def get_hash(filepath = Path):
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def execute():
    if actions_find.get():
        duplicate_finder()
        print("Finding duplicates...")
    if actions_water.get():
        watermark()
        print("Adding watermarks...")
    if actions_rename.get():
        rename()
        print("Renaming files...")
    if actions_sort.get():
        sort()
        print("Sorting...")

def middle_reset():
    for widget in middle.winfo_children():
        widget.grid_forget()

def organize_open():
    global actions_water
    global actions_find
    global actions_sort
    global middle
    global currently_open

    if currently_open == 0:
        ()
    else:
        middle_reset()
    middle.grid_columnconfigure(2, weight=1)
    middle.grid_rowconfigure(10, weight=1)
    middle.grid_rowconfigure(7, weight=0)
    organize_title.grid(sticky="nw", pady=18, padx=18)
    folder_frame.grid(row=3, sticky="ew", padx=30, column=0)
    folder_browser.grid(sticky="nw", pady=20, padx=(26,5), row=0, column=0)
    folder_chosen.grid(sticky="nw", pady=20, row=0, column=1)
    actions_title.grid(sticky="nw", padx=26, pady=(25,10), row=4)
    actions_find.grid(sticky="nw", padx=32, pady=(5,10), row=5)
    actions_sort.grid(sticky="nw", padx=32, pady=10, row=6)
    actions_water.grid(sticky="nw", padx=32, pady=10, row=7)
    actions_rename.grid(sticky="nw", padx=32, pady=10, row=8)
    execute_button.grid(row=9, column=0, padx=104)

    currently_open = 0 #(0 for organize, 1 for settings, 2 for tutorial)


def settings_open():
    global middle
    global currently_open
    if currently_open == 1:
        ()
    else:
        middle_reset()
        middle.grid_columnconfigure(0, weight=1)
        middle.grid_rowconfigure(7, weight=1)
        settings_label.grid(sticky="nw", pady=18, padx=18)
        find_settings.grid(row=3, column=0, padx=20, pady=12, sticky="ew")
        sort_settings.grid(row=4, column=0, padx=20, pady=12, sticky="ew")
        water_settings.grid(row=5, column=0, padx=20, pady=12, sticky="ew")
        rename_settings.grid(row=6, column=0, padx=20, pady=12, sticky="ew")
    currently_open = 1 #(0 for organize, 1 for settings, 2 for tutorial)
    
def tutorial_open():
    global middle
    global currently_open
    if currently_open == 2:
        ()
    else:
        middle_reset()
    tutorial_label.grid(sticky="nw", pady=18, padx=18)
    currently_open = 2 #(0 for organize, 1 for settings, 2 for tutorial)
#tk
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
canvas = ctk.CTk()
canvas.title("Specular")
canvas.geometry("1024x576")
canvas.resizable(width=False, height=False)
logo = ImageTk.PhotoImage(Image.open("specular_logo.png"))
canvas.after(500, lambda: canvas.iconphoto(False, logo))
check_messages()

#left
left = ctk.CTkFrame(canvas, width=200, height=576, fg_color="#1f2029", corner_radius=0)
left.grid(row = 0, column = 0)
left.grid_propagate(False)
left.grid_columnconfigure(0, weight=1)
left.grid_rowconfigure(10, weight=1)

left_title = ctk.CTkLabel(left, text="Specular", font=("Bahnschrift Light Condensed", 32))
left_title.grid(sticky="nw", pady=18, padx=18)

organize_button = ctk.CTkButton(left, text="Organize", font=("Bahnschrift Light Condencsed", 16), command=organize_open)
organize_button.grid(sticky="nw", pady=(36, 18), padx=18)

settings_button = ctk.CTkButton(left, text="Settings", font=("Bahnschrift Light Condencsed", 16), command=settings_open)
settings_button.grid(sticky="nw", pady=18, padx=18)

tutorial_button = ctk.CTkButton(left, text="Tutorial", font=("Bahnschrift Light Condencsed", 16), command=tutorial_open)
tutorial_button.grid(sticky="nw", pady=18, padx=18)

#middle
middle = ctk.CTkFrame(canvas, width=564, height=576, fg_color="#20222e", corner_radius=0)
middle.grid(row = 0, column = 1)
middle.grid_propagate(False)
middle.grid_columnconfigure(2, weight=1)
middle.grid_rowconfigure(10, weight=1)

#tutorial
tutorial_label = ctk.CTkLabel(middle, text="Tutorial", font=("Bahnschrift Light Condensed", 32))
tutorial_text1 = ctk.CTkLabel(middle, text="1. Pick a folder you want to clean\n2. Pick a function\n3. Wait for thprogram to finish\n4. Enjoy the saved time!", font=("Bahnschrift Light Condensed", 20))
tutorial_text2 = ctk.CTkLabel(middle, text="Functions", font=("Bahnschrift Light Condensed", 20))
tutorial_text4 = ctk.CTkLabel(middle, text="Sorts all the files in your chosen folder.\ndesired_folder/sorted/yeamonth/file", font=("Bahnschrift Light Condensed", 13))
tutorial_text5 = ctk.CTkLabel(middle, text="b) Finding duplicates", font=("Bahnschrift Light Condensed", 16))
tutorial_text6 = ctk.CTkLabel(middle, text="Finds all the duplicates in your chosen folder\nand puts them in separate folder.\ndesired_folder/duplicates/files", font=("Bahnschrift Light Condensed", 13))
tutorial_text7 = ctk.CTkLabel(middle, text="All changes all revertable and the duplicates aren't deleted.", font=("Bahnschrift Light Condensed", 12))

#settings
settings_label = ctk.CTkLabel(middle, text="Settings", font=("Bahnschrift Light Condensed", 32))

find_settings = ctk.CTkFrame(middle, width=364, height=56, fg_color="#1f2029")
find_settings.grid_rowconfigure(2, weight=1)
find_settings.grid_propagate(False)
find_settings.grid_columnconfigure(1, weight=1)
sort_settings = ctk.CTkFrame(middle, width=364, height=96, fg_color="#1f2029")
sort_settings.grid_rowconfigure(2, weight=1)
sort_settings.grid_propagate(False)
sort_settings.grid_columnconfigure(1, weight=1)
water_settings = ctk.CTkFrame(middle, width=364, height=136, fg_color="#1f2029")
water_settings.grid_rowconfigure(3, weight=1)
water_settings.grid_propagate(False)
water_settings.grid_columnconfigure(1, weight=1)
rename_settings = ctk.CTkFrame(middle, width=364, height=56, fg_color="#1f2029")
rename_settings.grid_rowconfigure(2, weight=1)
rename_settings.grid_propagate(False)
rename_settings.grid_columnconfigure(1, weight=1)

#Find Settings
settings_duplicate_delete_text = ctk.CTkLabel(find_settings, text="Duplicates are: ", font=("Bahnschrift Light Condencsed", 16))
settings_duplicate_delete = ctk.CTkOptionMenu(find_settings, values=["Moved to a folder", "Deleted"], font=("Bahnschrift Light Condencsed", 16), width=212, anchor="center")
settings_duplicate_delete.set("Moved to a folder")
settings_duplicate_delete_text.grid(padx=16, pady=8, row=0, column=0, sticky="w")
settings_duplicate_delete.grid(row=0, column=1, padx=16, pady=8, sticky="e")

#Sort Settings
settings_sort_structure_text = ctk.CTkLabel(sort_settings, text="Sorted structure: ", font=("Bahnschrift Light Condencsed", 16))
settings_sort_structure = ctk.CTkOptionMenu(sort_settings, values=["year/month/day", "year/month"], font=("Bahnschrift Light Condencsed", 16), width=212, anchor="center")
settings_sort_structure.set("year/month/day")

settings_sort_sortby_text = ctk.CTkLabel(sort_settings, text="Sort by: ", font=("Bahnschrift Light Condencsed", 16))
settings_sort_sortby = ctk.CTkOptionMenu(sort_settings, values=["Date taken", "Date modified"], font=("Bahnschrift Light Condencsed", 16), width=212, anchor="center")
settings_sort_sortby.set("Date taken")
settings_sort_sortby_text.grid(padx=16, pady=8, row=0, column=0, sticky="w")
settings_sort_sortby.grid(row=0, column=1, padx=16, pady=8, sticky="e")
settings_sort_structure_text.grid(padx=16, pady=8, row=1, column=0, sticky="w")
settings_sort_structure.grid(row=1, column=1, padx=16, pady=8, sticky="e")
#Rename Settings
def rename_pattern_changed(choice):
    if choice=="custom_name + number":
        rename_settings.configure(height=96)
        settings_rename_custom_text.grid(padx=16, pady=8, row=1, column=0, sticky="w")
        settings_rename_custom.grid(row=1, column=1, padx=16, pady=8, sticky="e")
    else:
        rename_settings.configure(height=56)
        settings_rename_custom_text.grid_forget()
        settings_rename_custom.grid_forget()
settings_rename_custom_text = ctk.CTkLabel(rename_settings, text="Custom name: ", font=("Bahnschrift Light Condencsed", 16))
settings_rename_custom = ctk.CTkTextbox(rename_settings, height=32, width=212)
settings_rename_pattern_text = ctk.CTkLabel(rename_settings, text="Renaming pattern: ", font=("Bahnschrift Light Condencsed", 16))
settings_rename_pattern = ctk.CTkOptionMenu(rename_settings, values=["date + number", "original name + number", "custom_name + number"], font=("Bahnschrift Light Condencsed", 16), command=rename_pattern_changed, width=212, anchor="center")
settings_rename_pattern.set("date + number")
settings_rename_pattern_text.grid(padx=16, pady=8, row=0, column=0, sticky="w")
settings_rename_pattern.grid(row=0, column=1, padx=16, pady=8, sticky="e")

#Watermark Settings

settings_watermark_image_text = ctk.CTkLabel(water_settings, text="Watermark image: ", font=("Bahnschrift Light Condencsed", 16))
settings_watermark_image = ctk.CTkButton(water_settings, width=212, text="Choose an image", font=("Bahnschrift Light Condencsed", 16), command=filedialog.askopenfile)
settings_watermark_corner_text = ctk.CTkLabel(water_settings, text="Watermark postition: ", font=("Bahnschrift Light Condencsed", 16))
settings_watermark_corner = ctk.CTkOptionMenu(water_settings, values=["Top Right", "Top Left", "Bottom Right", "Bottom Left", "Centre"], font=("Bahnschrift Light Condencsed", 16), width=212, anchor="center")
settings_watermark_corner.set("Top Right")

watermark_size_frame = ctk.CTkFrame(water_settings, fg_color="transparent")
watermark_size_frame.grid_columnconfigure(1, weight=1)
settings_watermark_size_text = ctk.CTkLabel(watermark_size_frame, text="Watermark size: ", font=("Bahnschrift Light Condencsed", 16))
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


set_wat_minus = ctk.CTkButton(watermark_size_subframe, text="-", command=minus, font=("Bahnschrift Light Condencsed", 16), width=49)
set_wat_plus = ctk.CTkButton(watermark_size_subframe, text="+", command=plus, font=("Bahnschrift Light Condencsed", 16), width=49)
set_wat_minus.grid(row=0,column=0, padx=(65,0), sticky="w")
settings_watermark_size.grid(row=0, column=1, padx=5, pady=8, sticky="w")
set_wat_plus.grid(row=0,column=2, padx=(0,16), sticky="w")
#organize
organize_title = ctk.CTkLabel(middle, text="Organize", font=("Bahnschrift Light Condensed", 30))
folder_frame = ctk.CTkFrame(middle, fg_color="#1f2029", height=32, width=324)
folder_browser = ctk.CTkButton(folder_frame, text="Choose a folder", command=pick_folder, font=("Bahnschrift Light Condensed", 18))
folder_chosen = ctk.CTkLabel(folder_frame, text="Folder chosen:", text_color="grey", font=("Bahnschrift Light Condensed", 14))
actions_title = ctk.CTkLabel(middle, text="Functions", text_color="grey", font=("Bahnschrift Light Condensed", 20))
actions_find = ctk.CTkCheckBox(middle, text="Find duplicates", font=("Bahnschrift Light Condensed", 16))
actions_water = ctk.CTkCheckBox(middle, text="Add watermark", font=("Bahnschrift Light Condensed", 16))
actions_sort = ctk.CTkCheckBox(middle, text="Sort files", font=("Bahnschrift Light Condensed", 16))
actions_rename = ctk.CTkCheckBox(middle, text="Rename files", font=("Bahnschrift Light Condensed", 16))
execute_button = ctk.CTkButton(middle, text="Execute", command=(run_execute), font=("Bahnschrift Light Condensed", 18), width=356, height=46)

#show tutorial
if tutorial_seen == 0:
    tutorial_open()
    tutorial_seen = 1
    try:
        with open("memory.json", "w") as f:
            json.dump(tutorial_seen, f)
    except FileNotFoundError:
        print("File not found.")
else:
    organize_open()

#right
right = ctk.CTkFrame(canvas, width=260, height=576, fg_color="#1f2029", corner_radius=0)
right.grid(row = 0, column = 2)
right.grid_propagate(False)
right.grid_columnconfigure(0, weight=1)
right.grid_rowconfigure(10, weight=1)

right_title = ctk.CTkLabel(right, text="Activity", font=("Bahnschrift Light Condensed", 30))
right_title.grid(sticky="nw", pady=18, padx=18)

status = ctk.CTkLabel(right, text="Sitting...", font=("Bahnschrift Light Condensed", 24), text_color="grey")
status.grid(row=2, sticky="nw", padx=20)
bar = ctk.CTkProgressBar(right)
q.put(("bar_hide", None))
bar_text = ctk.CTkLabel(right, text="")
q.put(("bar_text_hide", None))
canvas.mainloop()

#TODO: Continue working on settings, then finish the restore functions in organize. Add a rename and watermark functions
#play around with the custom name, add a checkbox to check whether its oki:>

"""
finished conditions:
duplicates: 1/1
sort: 0/2
watermark: 0/3
renaming: 0/1
"""