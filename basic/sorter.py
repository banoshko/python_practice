from pathlib import Path
folder = Path("files")
dict = {
    ".txt": "text files", ".json": "text files",
    ".png": "pictures", ".jpg": "pictures", ".jpeg": "pictures",
    ".zip": "compressed files"
}
position = 1
def item_sorter(folder, suffix, item, position):
    destination = folder/suffix
    destination.mkdir(exist_ok=True)
    absolute_destination = destination/item.suffix.lower().lstrip(".")
    absolute_destination.mkdir(exist_ok=True)
    item_destination = absolute_destination/item.name
    if item.exists():
        while item_destination.exists():
            str(position)
            q = Path(f"{item.stem}_{position}{item.suffix}")
            int(position)
            position += 1
            print(item)
            item_destination =  absolute_destination/q.name 
    item.rename(item_destination)
    
for item in folder.iterdir():
    if item.is_file():
        suffix = dict.get(item.suffix.lower(), "other")
        item_sorter(folder, suffix, item, position)

for items in folder.iterdir():
    print(f"You have {len(list(items.rglob('*.*')))} files in your {items.name} folder" if items.is_dir() else (""))