from pathlib import Path
folder = Path("files")
items_count = 0
dict = {
    ".txt": "text files", ".json": "text files",
    ".png": "pictures", ".jpg": "pictures", ".jpeg": "pictures",
    ".zip": "compressed files"
}
def item_sorter(folder, suffix, item):
    destination = folder/suffix
    destination.mkdir(exist_ok=True)
    item_destination = destination/item.name
    item.rename(item_destination)
    
for item in folder.iterdir():
    if item.is_file():
        suffix = dict.get(item.suffix.lower(), "other")
        item_sorter(folder, suffix, item)

counter = {}
for items in folder.iterdir():
    for _ in items.iterdir():
        items_count +=1
    counter[items.name] = items_count
    print(f"You have {counter[items.name]} files in your {items.name} folder")
    items_count = 0