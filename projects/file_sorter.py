#This is my attempt at making an actually sellable product.
#Not even 2 weeks into python at this point
#Start - Sunday, 27th Sep. 2026

from datetime import datetime
from pathlib import Path
import json
#import tkinter as tk


#User settings
target_folder = Path("files") #Use tk to let the user choose the folder
#target_folder = Path(r"C:\Users\richi\Downloads")
#Developer settings
dry_run = False

month_dict = { 
    1: "(1) January", 2: "(2) February", 3: "(3) March", 4: "(4) April", 5: "(5) May", 6: "(6) June", 7: "(7) July", 8: "(8) August", 9: "(9) September", 10: "(10) October", 11: "(11) November", 12: "(12) December"
} #folders get named properly
years_used = []
folder_size = sum(f.stat().st_size for f in target_folder.rglob("*") if f.is_file())/(1024*1024*1024)
print(folder_size)
#Script itself
for item in target_folder.iterdir():
    try:
        if str(item.stem) != years_used:
            year = str(datetime.fromtimestamp(item.stat().st_mtime).year)
            month = month_dict[datetime.fromtimestamp(item.stat().st_mtime).month]
            sorted = Path(target_folder/"sorted")
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
