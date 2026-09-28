#This is my attempt at making an actually sellable product.
#Not even 2 weeks into python at this point
#Start - Sunday, 27th Sep. 2026

from datetime import datetime
from pathlib import Path
import hashlib
import tkinter as tk
from tkinter import filedialog


#User settings
#target_folder = Path("files") #Use tk to let the user choose the folder
target_folder = Path(filedialog.askdirectory())
#Developer settings
dry_run = False

month_dict = { 
    1: "(1) January", 2: "(2) February", 3: "(3) March", 4: "(4) April", 5: "(5) May", 6: "(6) June", 7: "(7) July", 8: "(8) August", 9: "(9) September", 10: "(10) October", 11: "(11) November", 12: "(12) December"
} #folders get named properly
years_used = []
folder_size = sum(f.stat().st_size for f in target_folder.rglob("*") if f.is_file())/(1024*1024*1024)
sorted = Path(target_folder/"sorted")
seen = []
#Script itself
def sort():
    for item in target_folder.iterdir():
        try:
            if str(item.stem) != years_used:
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
    bin = Path(target_folder/"duplicates")
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
def restore_duplicate():
    if target_folder.name == "duplicates":
        for item in target_folder.iterdir():
            item.rename(target_folder.parent/item.name)
    else:
        for file in bin.iterdir():
            if file.is_file():
                file.rename(target_folder/file.name)
    

#Tkinter stuff

while True:
    try:
        user_input = int(input("1 for sorting, 2 for restoring sorted, 3 for finding duplicates, 4 for restoring duplicates: "))
        if user_input == 1:
            sort()
        if user_input == 2:
            restore_sort()
            break
        if user_input == 3:
            duplicate_finder()
        if user_input == 4:
            restore_duplicate()
        else:
            ()
    except ValueError: 
        print("You must enter a numeber.")
#Continue tommorow:
#Tkinter stuff