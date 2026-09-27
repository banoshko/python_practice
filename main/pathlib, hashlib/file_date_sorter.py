from pathlib import Path
from datetime import datetime

dry_run = False #Use for checking where items end up.
target_folder = Path(r"C:\Users\richi\Downloads")
#target_folder = Path("files")
years_possible = []
years_used = []
dict = {
    1: "(1) January", 2: "(2) February", 3: "(3) March", 4: "(4) April", 5: "(5) May", 6: "(6) June", 7: "(7) July", 8: "(8) August", 9: "(9) September", 10: "(10) October", 11: "(11) November", 12: "(12) December",
}
device_year = 2024

while device_year != int(datetime.today().strftime("%Y").split("-", 1)[0]):
    years_possible.append(device_year)
    device_year+=1
    
for item in target_folder.iterdir():

   
    try:
        if str(item.stem) not in years_possible:
            year = datetime.fromtimestamp(item.stat().st_mtime).year
            years_used.append(str(year))
            month = dict[datetime.fromtimestamp(item.stat().st_mtime).month]
            year_path = target_folder / str(year)
            year = Path(year_path)
            year_path.mkdir(exist_ok=True)
            month_path = year_path / month
            year = Path(month_path)
            month_path.mkdir(exist_ok=True)
            item.rename(month_path/item.name)
    except PermissionError:
        print(f"Not permitted to move file {item.name}.")
    except Exception:
        print("Something has gone wrong.")
"""
def revertion():
    while target_folder.iterdir() in years_used:
        if str(item.name) in str(years_used):
            ()
            print(f"{item} didnt move")
        elif item.is_file():
            item.rename(target_folder/item.name)
            print(f"Item {item} moved")
        else:
            for child in item.iterdir():
                if child.is_file():
                    child.rename(target_folder/child.name)
                    print(f"{child} moved")
                else:
                    for child_child in child.iterdir():
                            child_child.rename(target_folder/child_child.name)
                            print(f"{child_child} moved")
                try:
                    child.rmdir()
                    print(f"{child} removed")
                except Exception:
                    print(f"Couldn't remove {child}")
        for year in years_used:
            try:
                if Path(target_folder/year).is_dir():
                    remove = Path(target_folder / year)
                    remove.rmdir()
                    print(f"{remove} removed")
            except OSError:
                print("Directory not empty")            
    print("Everything back in its"""
def revertion():
    for item in target_folder.iterdir():
        if any(n == item for n in years_used):
             ()
        elif item.is_file():
            item.rename(target_folder/item.name)
        else:
            for child in item.iterdir():
                if child.is_file():
                    child.rename(target_folder/item.name)
                else:
                    for child_child in child.iterdir():
                        try:
                            child_child.rename(target_folder/child_child.name)
                        except PermissionError:
                            print("I wasn't able to move {child_child} due to access being denied.")    
    for folder in target_folder.iterdir():
        if folder.is_dir() and str(folder.stem) in str(years_used):
            for month_folder in folder.iterdir():
                month_folder.rmdir()
            folder.rmdir()
    print("Everything back in its place.")
            
while True:
    try:
        revert = int(input("Would you like to revert the changes? 1 for YES, 0 for NO: "))
        if revert == 1:
            revertion()
            break
        if revert == 0:
            print("Glad I could help!")
            break
        else:
            print("You must answer with 1 or 0.")
    except ValueError:
        print("You must enter a number.")