from pathlib import Path 
dry_run = True #Use for checking where items end up.
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
    renamed = False
    while item_destination.exists():
        q = Path(f"{item.stem}_{position}{item.suffix}")
        position += 1
        item_destination =  absolute_destination/q.name
        renamed = True
    if dry_run == False:
        item.rename(item_destination)
    else:
        print(f"I would move item {item_destination.name} into {item_destination}" if renamed == False else f"I would rename item {item.name} to {item_destination.name} and then move it into {item_destination}")
for item in folder.iterdir():
    if item.is_file():
        suffix = dict.get(item.suffix.lower(), "other")
        item_sorter(folder, suffix, item, position)

for items in folder.iterdir():
    print(f"You have {len(list(items.rglob('*.*')))} files in your {items.name} folder" if items.is_dir() else (""))