#This is my attempt at making an actually sellable product.
#Not even 2 weeks into python at this point
#Start - Sunday, 27th Sep. 2026

from datetime import datetime
from pathlib import Path
import hashlib
import tkinter as tk
from tkinter import filedialog
#Developer settings
dry_run = False
month_dict = {
    1: "(1) January", 2: "(2) February", 3: "(3) March", 4: "(4) April", 5: "(5) May", 6: "(6) June", 7: "(7) July", 8: "(8) August", 9: "(9) September", 10: "(10) October", 11: "(11) November", 12: "(12) December"
}
years_used = []

#Script itself
def sort():
    for item in target_folder.iterdir():
        try:
            if item.is_file() or item.is_dir() and item.name != "sorted":
                year = str(datetime.fromtimestamp(item.stat().st_mtime).year)
                month = month_dict[datetime.fromtimestamp(item.stat().st_mtime).month]
                sorted.mkdir(exist_ok=True)
                year_dir = sorted / year
                year_dir.mkdir(exist_ok=True)
                month_dir = year_dir / month
                month_dir.mkdir(exist_ok=True)
                years_used.append(year)
                if dry_run == False:
                    item.rename(month_dir/item.name)
                else:
                    print(f"Moving file {item.name} to {year}/{month}")
                try:
                    print(f"We're {sum(f.stat().st_size for f in sorted.rglob('*') if f.is_file())/(1024*1024*1024) / folder_size * 100 :.2f}% through!")
                except ZeroDivisionError:
                    ()
        except PermissionError:
            print(f"Not permitted to move {item.name}.")
    print("Files sorted.")

def restore_sort():
    if target_folder.name == "sorted":
        for year in target_folder.iterdir():
            for month in year.iterdir():
                for file in month.iterdir():
                    file.rename(target_folder.parent/file.name)
                month.rmdir()
            year.rmdir()
        target_folder.rmdir()
        print("Files restored")
    elif not sorted.exists():
        print("Nothing to restore")
    else:    
        for year in sorted.iterdir():
            for month in year.iterdir():
                for file in month.iterdir():
                    file.rename(target_folder/file.name)
                month.rmdir()
            year.rmdir()
        sorted.rmdir()
        print("Files restored")

def duplicate_finder():
    seen = []
    sizes = 0
    for item in target_folder.iterdir():
        if item.is_file():
            with open(item, "rb") as f:
                data = f.read()
                hash = hashlib.sha256(data).hexdigest()
            if hash in seen:
                if dry_run == True:
                    print("Duplicate")
                    print(f"DUPLICATE: {item.name.upper()} matches a file previously seen!")  
                    print("Duplicate")  
                elif dry_run == False:
                    bin.mkdir(exist_ok=True)
                    item.rename(bin/item.name)
            else:
                seen.append(hash)
            sizes = sizes + int(item.stat().st_size)
            try:
                print(f"We're {(sizes)/(1024*1024*1024) / folder_size * 100 :.2f}% through!")
            except ZeroDivisionError:
                ()
    if not bin.exists():
        print("YAY! No duplicates found!")

def restore_duplicate():
    if not bin.exists():
        print("Nothing to restore")
    elif target_folder.name == "duplicates":
        for item in target_folder.iterdir():
            item.rename(target_folder.parent/item.name)
    else:
        for file in bin.iterdir():
            if file.is_file():
                file.rename(target_folder/file.name)

def pick_folder():
    global target_folder
    global folder_size
    global bin
    global sorted

    chosen = filedialog.askdirectory()

    while True:
        if chosen:
            target_folder = Path(chosen)
            folder_browser.config(text = f"Selected: {target_folder.name}")
            break
        else:
            chosen = filedialog.askdirectory()

    folder_size = sum(f.stat().st_size for f in target_folder.rglob("*") if f.is_file())/(1024*1024*1024)
    sorted = Path(target_folder/"sorted")
    bin = Path(target_folder/"duplicates")

canvas = tk.Tk()
canvas.title("File sorter")
canvas.geometry("408x512")

text = tk.Label(canvas, text = "File sorter", font="24", pady = 50)
text.pack()

folder_browser = tk.Button(canvas, text = "Browse files", command = pick_folder)
folder_browser.pack(pady=10)

sort_button = tk.Button(canvas, text = "Sort files", command = sort)
sort_button.pack()

restore_sort_button = tk.Button(canvas, text = "Restore sorted files files", command = restore_sort)
restore_sort_button.pack()

duplicate_button = tk.Button(canvas, text = "Find duplicates", command = duplicate_finder)
duplicate_button.pack()

restore_duplicate_button = tk.Button(canvas, text = "Undo duplicate search", command = restore_duplicate)
restore_duplicate_button.pack()

canvas.mainloop()