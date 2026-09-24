import hashlib
from pathlib import Path

dry_run = False #Use for checking where items end up.
target_folder = Path(r"C:\Users\richi\Downloads")

bin = Path(fr"{target_folder}\duplicates")
bin.mkdir(exist_ok=True)
seen = []
suffix = []

for file in target_folder.iterdir():
    if file.is_file():
        with open(file, "rb") as f:
            data = f.read()
            hash = hashlib.sha256(data).hexdigest()
        if hash in seen:
            if dry_run == True:
                print("Duplicate")
                print(f"DUPLICATE: {file.name.upper()} matches a file previously seen!")   
                print("Duplicate")   
            elif dry_run == False:
                file.rename(bin/file.name)
        else:
            seen.append(hash)

def revert():
    for file in bin.iterdir():
        if file.is_file():
            file.rename(target_folder/file.name)

def rename():
    for file in bin.iterdir():
        suffix = ["(1)", "(2)", "(3)", "(4)", "(5)", "(6)", "(7)", "(8)", "(9)", "(10)", ]
        for target_file in target_folder.iterdir():
            if target_file.is_file():
                with open(target_file, "rb") as f:
                    data = f.read()
                    hash_target = hashlib.sha256(data).hexdigest()
                with open(file, "rb") as f:
                    data = f.read()
                    hash_bin = hashlib.sha256(data).hexdigest()
                if hash_bin == hash_target and any(suf in target_file.stem for suf in suffix):
                    final_target_name = f"{target_folder}/{target_file.stem.rsplit(' (', 1)[0]}{target_file.suffix}"
                    target_file.rename(final_target_name)

if dry_run == False:
    while True:
        try:
            print("Would you like to revert the changes and move the files back?")
            choice = int(input("1 for YES, 0 for NO: "))
            if choice == 1:
                revert()
                print("Files have been reverted.")
                bin.rmdir()
                break
            elif choice == 0:
                print("I'm glad I could help!")
                rename()
                break
            else:
                print("Invalid number.")
        except ValueError:
            print("You must enter a number!")