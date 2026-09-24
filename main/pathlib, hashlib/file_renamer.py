from pathlib import Path
dry_run = False #Use for checking where items end up.
folder = Path("files")
cycle = 0
renamed = {}
for file_original in folder.iterdir():
    new_file = folder / f"{cycle}_{file_original.name}"
    if file_original.is_file():
        cycle += 1
        if dry_run == True:
            print(f"I'd rename item {file_original} to {new_file}")
        else:
            renamed[new_file] = file_original
            file_original.rename(new_file)

def restore():
    for file in renamed.keys():
        if file.is_file():
            file_default = renamed[file]
            file.rename(file_default)

while True:
    try:
        user = int(input("Would you like to restore the old names? 1 for YES, 0 for NO: "))
        if user == 1:
            restore()
            break
        if user == 0:
            print("Oki bye")
            break
    except ValueError:
        print("You must enter a number.")
    