from pathlib import Path
dict = {
    ".txt": "text files", ".json": "text files",
    ".png": "pictures", ".jpg": "pictures", ".jpeg": "pictures",
    ".zip": "compressed files"
}
folder = Path("files")
def transport_files(folder, suffix, item):
    destination = Path(folder/suffix)
    destination.mkdir(exist_ok=True)
    item_destination = destination/item.name
    item.rename(item_destination)
for item in folder.iterdir():
    if item.is_file():
        suffix = dict.get(item.suffix.lower())
        transport_files(folder, suffix, item)