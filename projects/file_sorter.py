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
suffix = [
    "(1)", "(2)", "(3)", "(4)", "(5)", "(6)", "(7)", "(8)", "(9)", "(10)"
]
#Script itself
def sort():
    try:
        for item in target_folder.iterdir():
            try:
                if item.is_file() or item.is_dir() and item.name != "sorted":
                    year = str(datetime.fromtimestamp(item.stat().st_mtime).year)
                    month = month_dict[datetime.fromtimestamp(item.stat().st_mtime).month]
                    sorted_dir.mkdir(exist_ok=True)
                    year_dir = sorted_dir / year
                    year_dir.mkdir(exist_ok=True)
                    month_dir = year_dir / month
                    month_dir.mkdir(exist_ok=True)
                    years_used.append(year)
                    if dry_run == False:
                        item.rename(month_dir/item.name)
                    else:
                        print(f"Moving file {item.name} to {year}/{month}")
                    try:
                        print(f"We're {sum(f.stat().st_size for f in sorted_dir.rglob('*') if f.is_file())/(1024*1024*1024) / folder_size * 100 :.2f}% through!")
                    except ZeroDivisionError:
                        ()
            except PermissionError:
                print(f"Not permitted to move {item.name}.")
        print("Files sorted.")
    except NameError:
        print("You must pick a folder.")
    except FileNotFoundError:
        print("File not found.")

def restore_sort():
    try:
        if target_folder.name == "sorted":
            for year in target_folder.iterdir():
                for month in year.iterdir():
                    for file in month.iterdir():
                        file.rename(target_folder.parent/file.name)
                    month.rmdir()
                year.rmdir()
            target_folder.rmdir()
            print("Files restored")
        elif not sorted_dir.exists():
            print("Nothing to restore")
        else:    
            for year in sorted_dir.iterdir():
                for month in year.iterdir():
                    for file in month.iterdir():
                        file.rename(target_folder/file.name)
                    month.rmdir()
                year.rmdir()
            sorted_dir.rmdir()
            print("Files restored")
    except NameError:
        print("You must pick a folder.")
    except FileNotFoundError:
        print("File not found.")

def duplicate_finder():
    try:
        seen = {}
        size = 0
        for item in target_folder.iterdir():
            if item.is_file():
                hash = get_hash(item)
                try:
                    size = size + item.stat().st_size / (1024*1024*1024)
                except FileNotFoundError:
                    print(f"File {item.name} not found")

                if hash in seen:
                    if any(suf in seen[hash].stem for suf in suffix):
                        duplicates.mkdir(exist_ok=True)
                        if any(suf in item.stem for suf in suffix):
                            item.rename(duplicates/item.name)
                        else:
                            seen[hash].rename(duplicates/seen[hash].name)
                            seen[hash] = Path(item)
                else:
                    seen[hash] = Path(item)

                try:
                    print(f"We're {(size) / folder_size * 100 :.2f}% through!")
                except ZeroDivisionError:
                    ()
            else:
                try:
                    size = size + sum(f.stat().st_size for f in item.rglob("*")) / (1024*1024*1024)
                except FileNotFoundError:
                    print(f"File {item.name} not found")
        
        if not duplicates.exists():
            print("YAY! No duplicates found!")
        else:
            print("Found all the duplicates")
        
    except NameError:
        print("You must pick a folder.")
    except FileNotFoundError:
        print("File not found.")

def restore_duplicate():
    try:
        if target_folder.name == "duplicates":
            for item in target_folder.iterdir():
                item.rename(target_folder.parent/item.name)
            target_folder.rmdir()
        elif not duplicates.exists():
            print("Nothing to restore")
        else:
            for file in duplicates.iterdir():
                if file.is_file():
                    file.rename(target_folder/file.name)
            duplicates.rmdir()
    except NameError:
        print("You must pick a folder.")
    except FileNotFoundError:
        print("File not found.")
    print("Restored.")

def pick_folder():
    global target_folder
    global folder_size
    global duplicates
    global sorted_dir

    chosen = filedialog.askdirectory()

    while True:
        if chosen:
            target_folder = Path(chosen)
            folder_browser.config(text = f"Selected: {target_folder.name}")
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

#tk

canvas = tk.Tk()
canvas.title("File sorter")
canvas.geometry("408x512")
canvas.resizable(width=False, height=False)

header = tk.Frame(canvas)
header.pack()
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

#TODO: Learn TK finally, make the ugly files go in the bin :>


"""

                if hash in seen:
                    if dry_run == True:
                        print("Duplicate")
                        print(f"DUPLICATE: {item.name.upper()} matches a file previously seen!")  
                        print("Duplicate")  
                    elif dry_run == False:
                        if not any(suf in item.stem for suf in suffix):
                            for i in duplicates.iterdir():
                                if get_hash(i) == hash and any(suf in i.stem for suf in suffix):
                                    copy_path = Path(i)
                                    i.rename(Path(item))
                                    item.rename(copy_path)
                        else:
                            duplicates.mkdir()
                            item.rename(duplicates/item.name)
                else:
                    seen.append(hash)
"""