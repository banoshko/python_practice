from pathlib import Path
files = [
    "a.txt", "B.txt", "C.TXT", "d.PNG", "E.jPeG", "f.Zip", "g.json", "H.jpG"
]
folder = Path("files")
folder.mkdir(exist_ok=True)
for file in files:
    save_files_as = folder/file
    save_files_as.touch()