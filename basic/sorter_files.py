from pathlib import Path
files = [
    "a.txt", "B.txt", "C.TXT", "d.PNG", "E.jPeG", "f.Zip", "g.json", "H.jpG", "i.bit", "j.PdF, K.Json", "l.pNG", "m.ZIP"
]
folder = Path("files")
folder.mkdir(exist_ok=True)
for file in files:
    file_creator = folder/file
    file_creator.touch()