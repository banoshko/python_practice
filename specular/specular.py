#This is my attempt at making an actually sellable product.
#Not even 2 weeks into python at this point
#Start - Sunday, 27th Sep. 2026

from datetime import datetime
from pathlib import Path
import hashlib
import customtkinter as ctk
from tkinter import filedialog
import random
import json

#Developer settings
month_dict = {
    1: "(1) January", 2: "(2) February", 3: "(3) March", 4: "(4) April", 5: "(5) May", 6: "(6) June", 7: "(7) July", 8: "(8) August", 9: "(9) September", 10: "(10) October", 11: "(11) November", 12: "(12) December"
}
years_used = []
suffix = [
    "(1)", "(2)", "(3)", "(4)", "(5)", "(6)", "(7)", "(8)", "(9)", "(10)"
]
lines = ["What a mess!", "Working on it!"]
basic = "Sitting..." #what the idle status says
tutorial = None
menu = None
#Script itself
def sort():
    line = random.choice(lines)
    try:
        bar = ctk.CTkProgressBar(right)
        bar.grid(row=3, padx=20)
        bar.set(0)
        canvas.update_idletasks()
        bar_text = ctk.CTkLabel(right, text="")
        bar_text.grid(row=4)
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
                    item.rename(month_dir/item.name)
                    try:
                        percent = sum(f.stat().st_size for f in sorted_dir.rglob('*') if f.is_file())/(1024*1024*1024) / folder_size * 100

                        if percent > 80:
                            status.configure(text="Almost there!")
                        else:
                            status.configure(text=f"{line}")
                        bar_text.configure(text = f"{percent :.2f}%")
                        bar.set(percent/100)
                        canvas.update_idletasks()
                    except ZeroDivisionError:
                        ()
            except PermissionError:
                print(f"Not permitted to move {item.name}.")
        bar_text.configure(text = "100%")
        status.configure(text="Files sorted!")
        canvas.update_idletasks()
        bar_text.after(3000)
        bar_text.destroy()
        bar.destroy()
        print("Files sorted.")
    except NameError:
        print("You must pick a folder.")
        bar_text.destroy()
        bar.destroy()
        status.configure(text = "You must pick a folder.")
        canvas.update_idletasks()
        status.after(1700)
        status.configure(text=basic)
        canvas.update_idletasks()
    except FileNotFoundError:
        print("File not found.")
        bar_text.destroy()
        bar.destroy()
    status.configure(text=basic)
    canvas.update_idletasks()
    
def restore_sort():
    try:
        if target_folder.name == "sorted":
            status.configure(text="Restoring sorted files...")
            canvas.update_idletasks()
            for year in target_folder.iterdir():
                for month in year.iterdir():
                    for file in month.iterdir():
                        file.rename(target_folder.parent/file.name)
                    month.rmdir()
                year.rmdir()
            target_folder.rmdir()
            status.after(500)
            status.configure(text="Everything back in its place!")
            canvas.update_idletasks()
            status.after(3000)
            status.configure(text=basic)
            canvas.update_idletasks()
        elif not sorted_dir.exists():
            status.configure(text="Nothing to restore.")
            canvas.update_idletasks()
            status.after(3000)
        else:
            status.configure(text="Restoring sorted files...")  
            canvas.update_idletasks()  
            for year in sorted_dir.iterdir():
                for month in year.iterdir():
                    for file in month.iterdir():
                        file.rename(target_folder/file.name)
                    month.rmdir()
                year.rmdir()
            sorted_dir.rmdir()
            status.after(500)
            status.configure(text="Everything back in its place!")
            canvas.update_idletasks()
            status.after(3000)
    
    except NameError:
        print("You must pick a folder.")
        status.configure(text = "You must pick a folder.")
        canvas.update_idletasks()
        status.after(1700)
    except FileNotFoundError:
        print("File not found.")
    except PermissionError:
        print("Not allowed to move this file.")
    status.configure(text=basic)
    canvas.update_idletasks()

def duplicate_finder():
    line = random.choice(lines)
    try:
        bar = ctk.CTkProgressBar(right)
        bar.grid(row=3, padx=20)
        canvas.update_idletasks()
        bar_text = ctk.CTkLabel(right, text="")
        seen = {}
        size = 0
        for item in target_folder.iterdir():
            bar.set(0)
            bar_text.grid(row=4)
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
                    percent = size / folder_size * 100

                    if percent > 80:
                        status.configure(text="Almost there!")
                    else:
                        status.configure(text=f"{line}")
                    bar_text.configure(text = f"{percent :.2f}%")
                    bar.set(percent/100)
                    canvas.update_idletasks()
                except ZeroDivisionError:
                    ()
            else:
                try:
                    size = size + sum(f.stat().st_size for f in item.rglob("*")) / (1024*1024*1024)
                except FileNotFoundError:
                    print(f"File {item.name} not found")
        
        if not duplicates.exists():
            bar_text.destroy()
            bar.destroy()
            status.configure(text="No duplicates found!")
            canvas.update_idletasks()
            status.after(3000)
        else:
            bar_text.configure(text = "100%")
            status.configure(text="All duplicates found!")
            canvas.update_idletasks()
            bar_text.after(3000)
            bar_text.destroy()
            bar.destroy()
    except NameError:
        bar_text.destroy()
        bar.destroy()
        canvas.update_idletasks()
        status.configure(text = "You must pick a folder.")
        canvas.update_idletasks()
        status.after(1700)
    except FileNotFoundError:
        bar_text.destroy()
        bar.destroy()
    status.configure(text=basic)
    canvas.update_idletasks()

def restore_duplicate():
    try:
        if target_folder.name == "duplicates":
            status.configure(text="Restoring duplicates...")  
            canvas.update_idletasks() 
            for item in target_folder.iterdir():
                item.rename(target_folder.parent/item.name)
            target_folder.rmdir()
            status.after(500)
            status.configure(text="Everything back in its place!")
            canvas.update_idletasks()
            status.after(3000)
    
        elif not duplicates.exists():
            status.configure(text="Nothing to restore.")
            canvas.update_idletasks()
            status.after(3000)
        else:
            status.configure(text="Restoring duplicates...")  
            canvas.update_idletasks() 
            for file in duplicates.iterdir():
                if file.is_file():
                    file.rename(target_folder/file.name)
            duplicates.rmdir()
            status.after(500)
            status.configure(text="Everything back in its place!")
            canvas.update_idletasks()
            status.after(3000)
    
    except NameError:
        print("You must pick a folder.")
        status.configure(text = "You must pick a folder.")
        canvas.update_idletasks()
        status.after(1700)
    except FileNotFoundError:
        print("File not found.")
    status.configure(text=basic)
    canvas.update_idletasks()

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

def tutorial_open():
    global tutorial
    if tutorial is None or not tutorial.winfo_exists():
        tutorial = ctk.CTkToplevel()
        tutorial.geometry("357x448")
        tutorial.title("Tutorial")
        tutorial.resizable(False, False)
        tutorial.lift()
        tutorial_label = ctk.CTkLabel(tutorial, text="Welcome to file sorter!", font=("times new roman", 32))
        tutorial_label.pack(pady=(10,15))
        tutorial_text1 = ctk.CTkLabel(tutorial, text="1. Pick a folder you want to clean\n2. Pick a function\n3. Wait for the program to finish\n4. Enjoy the saved time!", font=("", 20))
        tutorial_text1.pack()
        tutorial_text2 = ctk.CTkLabel(tutorial, text="Functions", font=("", 20))
        tutorial_text2.pack(pady=(25,0))
        tutorial_text3 = ctk.CTkLabel(tutorial, text="a) File sorting", font=("", 16))
        tutorial_text3.pack()
        tutorial_text4 = ctk.CTkLabel(tutorial, text="Sorts all the files in your chosen folder.\ndesired_folder/sorted/year/month/file", font=("", 13))
        tutorial_text4.pack(pady=(0,10))
        tutorial_text5 = ctk.CTkLabel(tutorial, text="b) Finding duplicates", font=("", 16))
        tutorial_text5.pack()
        tutorial_text6 = ctk.CTkLabel(tutorial, text="Finds all the duplicates in your chosen folder\nand puts them in a separate folder.\ndesired_folder/duplicates/files", font=("", 13))
        tutorial_text6.pack(pady=(0,10))
        tutorial_text7 = ctk.CTkLabel(tutorial, text="All changes all revertable and the duplicates aren't deleted.", font=("Roboto Bold", 12))
        tutorial_text7.pack(pady=(15,5))

        tutorial_close = ctk.CTkButton(tutorial, text="Got it", command=tutorial.destroy)
        tutorial_close.pack()
        tutorial.lift()
    else:
        tutorial.lift()

#tk
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
canvas = ctk.CTk()
canvas.title("Specular")
canvas.geometry("1024x576")
canvas.resizable(width=False, height=False)


#left
left = ctk.CTkFrame(canvas, width=200, height=576, fg_color="#1f2029", corner_radius=0)
left.grid(row = 0, column = 0)
left.grid_propagate(False)
left.grid_columnconfigure(0, weight=1)
left.grid_rowconfigure(10, weight=1)

left_title = ctk.CTkLabel(left, text="Specular", font=("Bahnschrift Light Condensed", 32))
left_title.grid(sticky="nw", pady=18, padx=18)

#middle
middle = ctk.CTkFrame(canvas, width=564, height=576, fg_color="#20222e", corner_radius=0)
middle.grid(row = 0, column = 1)
middle.grid_propagate(False)
middle.grid_columnconfigure(1, weight=1)
middle.grid_rowconfigure(10, weight=1)

#organize

organize_title = ctk.CTkLabel(middle, text="Organize", font=("Bahnschrift Light Condensed", 30))
organize_title.grid(sticky="nw", pady=18, padx=18)

folder_browser = ctk.CTkButton(middle, text="Choose a folder", command=pick_folder)
folder_browser.grid(sticky="nw", pady=20, padx=(26,10), row=3, column=0)
folder_chosen = ctk.CTkLabel(middle, text="Folder chosen:", font=("", 12), text_color="grey")
folder_chosen.grid(sticky="nw", pady=20, row=3, column=1)


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

#tutorial
try:
    with open("memory.json", "r") as f:
        tutorial_seen = json.load(f)
except FileNotFoundError:
    print("File not found.")

if tutorial_seen == 0:
    tutorial_open()
    tutorial_seen = 1
    try:
        with open("memory.json", "w") as f:
            json.dump(tutorial_seen, f)
    except FileNotFoundError:
        print("File not found.")
canvas.mainloop()


#TODO: Learn TK finally, v menu, ked pouzivatel vyberie tlacidlo, nech sa menu schová a príde to, čo chceli