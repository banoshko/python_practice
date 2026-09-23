# Test 6: Pathlib fundamentals
# Task: Create folder+files, list files only, print name+extension, avoid overwriting duplicates.
# Time limit: 15 min

from pathlib import Path

folder = Path("pathlib_test")
folder.mkdir(exist_ok=True)

files = [
    "a.txt", "b.jpg", "c.png", "d.zip"
]

for file in files:
        destination = folder/file
        if destination.exists():
             print(f"{file} already exists in {folder}")
        else:
            destination.touch()
for i in folder.iterdir():
    if i.is_file():
        print(i.name)
        print(i.suffix)

#Time: 9:38
#Readability: 8/10
#Improvability: 9/10