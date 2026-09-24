from pathlib import Path

files = [
    "a.txt", "B.txt", "C.TXT", "d.PNG", "E.jPeG", "f.Zip", "g.json", "H.jpG", "i.bit", "j.PdF", "K.Json", "l.pNG", 
    "m.ZIP"
]
folder = Path("files")
folder.mkdir(exist_ok=True)
for file in files:
    position = 1
    file_creator = folder/file
    while file_creator.exists():
        q = Path(f"{Path(file).stem}_{position}{Path(file).suffix}")
        position += 1
        file_creator =  folder/q.name 
    file_creator.touch()